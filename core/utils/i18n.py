import os
import re
from collections.abc import MutableMapping
from decimal import Decimal, ROUND_HALF_UP
from string import Template
from typing import Any, Dict, Optional, Tuple, Union

import orjson as json

from config import Config
from .text import isint, remove_suffix

default_locale = Config('locale', 'zh_cn')

# Load all locale files into memory

# We might change this behavior in the future and read them on demand as
# locale files get too large


class LocaleNode:
    """本地化树节点"""
    value: str
    children: dict

    def __init__(self, v: str = None):
        self.value = v
        self.children = {}

    def query_node(self, path: str):
        """查询本地化树节点"""
        return self._query_node(path.split('.'))

    def _query_node(self, path: list):
        """通过路径队列查询本地化树节点"""
        if len(path) == 0:
            return self
        nxt_node = path[0]
        if nxt_node in self.children.keys():
            return self.children[nxt_node]._query_node(path[1:])
        else:
            return None

    def update_node(self, path: str, write_value: str):
        """更新本地化树节点"""
        return self._update_node(path.split('.'), write_value)

    def _update_node(self, path: list, write_value: str):
        """通过路径队列更新本地化树节点"""
        if len(path) == 0:
            self.value = write_value
            return
        nxt_node = path[0]
        if nxt_node not in self.children.keys():
            self.children[nxt_node] = LocaleNode()
        self.children[nxt_node]._update_node(path[1:], write_value)


locale_root = LocaleNode()


# From https://stackoverflow.com/a/6027615
def flatten(d: Dict[str, Any], parent_key='', sep='.'):
    items = []
    for k, v in d.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, MutableMapping):
            items.extend(flatten(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def load_locale_file():
    locale_dict = {}
    err_prompt = []
    locales_path = os.path.abspath('./locales')
    locales = os.listdir(locales_path)
    try:
        for l in locales:
            with open(f'{locales_path}/{l}', 'r', encoding='utf-8') as f:
                locale_dict[remove_suffix(l, '.json')] = flatten(json.loads(f.read()))
    except Exception as e:
        err_prompt.append(str(e))
    modules_path = os.path.abspath('./modules')
    for m in os.listdir(modules_path):
        if os.path.isdir(f'{modules_path}/{m}/locales'):
            locales_m = os.listdir(f'{modules_path}/{m}/locales')
            for lang_file in locales_m:
                lang_file_path = f'{modules_path}/{m}/locales/{lang_file}'
                with open(lang_file_path, 'r', encoding='utf-8') as f:
                    try:
                        if remove_suffix(lang_file, '.json') in locale_dict:
                            locale_dict[remove_suffix(lang_file, '.json')].update(flatten(json.loads(f.read())))
                        else:
                            locale_dict[remove_suffix(lang_file, '.json')] = flatten(json.loads(f.read()))
                    except Exception as e:
                        err_prompt.append(f'Failed to load {lang_file_path}: {e}')
    for lang in locale_dict.keys():
        for k in locale_dict[lang].keys():
            locale_root.update_node(f'{lang}.{k}', locale_dict[lang][k])
    return err_prompt


def get_available_locales():
    return list(locale_root.children.keys())


class Locale:
    def __init__(self, locale: str, fallback_lng=None):
        """创建一个本地化对象"""
        if not fallback_lng:
            fallback_lng = ['zh_cn', 'zh_tw', 'en_us']
        self.locale = locale
        self.data: LocaleNode = locale_root.query_node(locale)
        self.fallback_lng = fallback_lng

    def __getitem__(self, key: str):
        return self.data[key]

    def __contains__(self, key: str):
        return key in self.data

    def get_locale_node(self, path: str):
        """获取本地化节点"""
        return self.data.query_node(path)

    def get_string_with_fallback(self, key: str, fallback_failed_prompt) -> str:
        node = self.data.query_node(key)
        if node:
            return node.value  # 1. 如果本地化字符串存在，直接返回
        fallback_lng = list(self.fallback_lng)
        fallback_lng.insert(0, self.locale)
        for lng in fallback_lng:
            if lng in locale_root.children:
                node = locale_root.query_node(lng).query_node(key)
                if node:
                    return node.value  # 2. 如果在 fallback 语言中本地化字符串存在，直接返回
        if fallback_failed_prompt:
            return f'{{{key}}}' + self.t("error.i18n.fallback", fallback_failed_prompt=False)
        else:
            return key
        # 3. 如果在 fallback 语言中本地化字符串不存在，返回 key

    def t(self, key: Union[str, dict], fallback_failed_prompt=True, *args, **kwargs) -> str:
        """获取本地化字符串"""
        if isinstance(key, dict):
            if ft := key.get(self.locale):
                return ft
            elif 'fallback' in key:
                return key['fallback']
            else:
                return str(key) + self.t("error.i18n.fallback", fallback=self.locale)
        localized = self.get_string_with_fallback(key, fallback_failed_prompt)
        return Template(localized).safe_substitute(*args, **kwargs)

    def t_str(self, text: str, fallback_failed_prompt=False) -> str:
        if locale_str := re.findall(r'\{(.*)}', text):
            for l in locale_str:
                text = text.replace(f'{{{l}}}', self.t(l, fallback_failed_prompt=fallback_failed_prompt))
        return text

    def int(self, number: Union[Decimal, int, str], precision: int = 0) -> str:
        """格式化数字"""
        if isint(number):
            number = int(number)
        else:
            return str(number)

        if self.locale in ['zh_cn', 'zh_tw']:
            unit_info = self._get_cjk_unit(number)
        else:
            unit_info = self._get_unit(number)

        if not unit_info:
            return str(number)

        unit, scale = unit_info
        fmted_num = self._fmt_num(number / scale, precision)
        return self.t_str(f"{fmted_num} {{i18n.unit.{unit}}}")

    def _get_cjk_unit(self, number: Decimal) -> Optional[Tuple[int, Decimal]]:
        if number >= Decimal('10e11'):
            return 3, Decimal('10e11')
        elif number >= Decimal('10e7'):
            return 2, Decimal('10e7')
        elif number >= Decimal('10e3'):
            return 1, Decimal('10e3')
        else:
            return None

    def _get_unit(self, number: Decimal) -> Optional[Tuple[int, Decimal]]:
        if number >= Decimal('10e8'):
            return 3, Decimal('10e8')
        elif number >= Decimal('10e5'):
            return 2, Decimal('10e5')
        elif number >= Decimal('10e2'):
            return 1, Decimal('10e2')
        else:
            return None

    def _fmt_num(self, number: Decimal, precision: int) -> str:
        number = number.quantize(Decimal(f"1.{'0' * precision}"), rounding=ROUND_HALF_UP)
        num_str = f"{number:.{precision}f}".rstrip('0').rstrip('.')
        return num_str if precision > 0 else str(int(number))


__all__ = ['Locale', 'load_locale_file', 'get_available_locales', 'default_locale']
