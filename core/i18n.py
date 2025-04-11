import glob
import html
import os
import re
import traceback
from collections.abc import MutableMapping
from decimal import Decimal, ROUND_HALF_UP
from string import Template
from typing import Any, Dict, List, Optional, Tuple, Union

import orjson as json

from core.constants.default import lang_list
from core.constants.path import locales_path, modules_locales_path
from .utils.text import isint

# Load all locale files into memory

# We might change this behavior in the future and read them on demand as
# locale files get too large

supported_locales = list(lang_list.keys())


class LocaleNode:
    """本地化树节点"""

    value: str
    children: dict

    def __init__(self, v: str = None):
        self.value = v
        self.children = {}

    def query_node(self, path: str):
        """查询本地化树节点"""
        return self._query_node(path.split("."))

    def _query_node(self, path: List[str]):
        """通过路径队列查询本地化树节点"""
        if len(path) == 0:
            return self
        nxt_node = path[0]
        if nxt_node in self.children:
            return self.children[nxt_node]._query_node(path[1:])
        return None

    def update_node(self, path: str, write_value: str):
        """更新本地化树节点"""
        return self._update_node(path.split("."), write_value)

    def _update_node(self, path: List[str], write_value: str):
        """通过路径队列更新本地化树节点"""
        if len(path) == 0:
            self.value = write_value
            return
        nxt_node = path[0]
        if nxt_node not in self.children:
            self.children[nxt_node] = LocaleNode()
        self.children[nxt_node]._update_node(path[1:], write_value)


locale_root = LocaleNode()

# From https://stackoverflow.com/a/6027615


def flatten(d: Dict[str, Any], parent_key="", sep="."):
    items = []
    for k, v in d.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, MutableMapping):
            items.extend(flatten(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def load_locale_file() -> List[str]:
    locale_dict = {}
    err_prompt = []

    locales = os.listdir(locales_path)
    try:
        for loc in locales:
            with open(os.path.join(locales_path, loc), "r", encoding="utf-8") as f:
                locale_dict[loc.removesuffix(".json")] = flatten(json.loads(f.read()))
    except Exception as e:
        traceback.print_exc()
        err_prompt.append(str(e))

    for modules_locales_file in glob.glob(modules_locales_path):
        if os.path.isdir(modules_locales_file):
            locales_m = os.listdir(modules_locales_file)
            for lang_file in locales_m:
                lang_file_path = os.path.join(modules_locales_file, lang_file)
                with open(lang_file_path, "r", encoding="utf-8") as f:
                    try:
                        if lang_file.removesuffix(".json") in locale_dict:
                            locale_dict[lang_file.removesuffix(".json")].update(
                                flatten(json.loads(f.read()))
                            )
                        else:
                            locale_dict[lang_file.removesuffix(".json")] = flatten(
                                json.loads(f.read())
                            )
                    except Exception as e:
                        traceback.print_exc()
                        err_prompt.append(f"Failed to load {lang_file_path}: {e}")

    for lang in locale_dict:
        for k in locale_dict[lang].keys():
            locale_root.update_node(f"{lang}.{k}", locale_dict[lang][k])

    return err_prompt


def get_available_locales() -> List[str]:
    return list(locale_root.children.keys())


class Locale:
    """
    创建一个本地化对象。
    """

    def __init__(self, locale: str, fallback_lng: Optional[List[str]] = None):
        if not fallback_lng:
            fallback_lng = supported_locales.copy()
            fallback_lng.remove(locale)
        self.locale = locale
        self.data: LocaleNode = locale_root.query_node(locale)
        self.fallback_lng = fallback_lng

    def __getitem__(self, key: str):
        return self.data.query_node(key)

    def __contains__(self, key: str):
        return key in self.data

    def get_locale_node(self, path: str):
        """获取本地化节点。"""
        return self.data.query_node(path)

    def get_string_with_fallback(
        self, key: str, fallback_failed_prompt: bool = True
    ) -> str:
        node = self.data.query_node(key)
        if node:
            return node.value  # 1. 如果本地化字符串存在，直接返回
        fallback_lng = list(self.fallback_lng)
        fallback_lng.insert(0, self.locale)
        for lng in fallback_lng:
            if lng in locale_root.children:
                node = locale_root.query_node(lng).query_node(key)
                if node:
                    return (
                        node.value
                    )  # 2. 如果在 fallback 语言中本地化字符串存在，直接返回
        if fallback_failed_prompt:
            return f"{{{key}}}" + self.t(
                "error.i18n.fallback", fallback_failed_prompt=False
            )
        return key
        # 3. 如果在 fallback 语言中本地化字符串不存在，返回 key

    def t(
        self, key: Union[str, dict], fallback_failed_prompt: bool = True, **kwargs: Any
    ) -> str:
        """
        获取本地化字符串。

        :param key: 本地化键名。
        :param fallback_failed_prompt: 是否添加本地化失败提示。（默认为True）
        :returns: 本地化字符串。
        """
        if isinstance(key, dict):
            if ft := key.get(self.locale):
                return ft
            if "fallback" in key:
                return key["fallback"]
            return str(key) + self.t("error.i18n.fallback", fallback=self.locale)
        localized = self.get_string_with_fallback(key, fallback_failed_prompt)
        return Template(localized).safe_substitute(**kwargs)

    def t_str(
        self, text: str, fallback_failed_prompt: bool = False, **kwargs: Dict[str, Any]
    ) -> str:
        """
        替换字符串中的本地化键名。

        :param text: 字符串。
        :param fallback_failed_prompt: 是否添加本地化失败提示。（默认为False）
        :returns: 本地化后的字符串。
        """
        text = self._match_i18ncode(text)

        if locale_str := re.findall(r"\{(.*)}", text):
            for lc in locale_str:
                text = text.replace(
                    f"{{{lc}}}",
                    self.t(lc, fallback_failed_prompt=fallback_failed_prompt, **kwargs),
                )

        text = self._match_i18ncode(text)

        return text

    def _match_i18ncode(self, text: str) -> str:
        split_all = re.split(r"(\[I18N:.*?])", text)
        split_all = [x for x in split_all if x]
        msgs = []
        kwargs = {}

        for e in split_all:
            match = re.match(r"\[I18N:([^\s,\]]+)(?:,([^\]]+))?\]", e)
            if not match:
                msgs.append(e)
            else:
                i18nkey = html.unescape(match.group(1))

                if match.group(2):
                    params = match.group(2).split(",")
                    params = [x for x in params if x]
                    for a in params:
                        ma = re.match(r"(.*?)=(.*)", a)
                        if ma:
                            kwargs[html.unescape(ma.group(1))] = html.unescape(ma.group(2))
                t_value = self.t(i18nkey, **kwargs)
                msgs.append(t_value if isinstance(t_value, str) else match.group(0))

        return "".join(msgs)

    def num(
        self,
        number: Union[Decimal, int, str],
        precision: int = 0,
        fallback_failed_prompt: bool = False,
    ) -> str:
        """
        格式化数字。

        :param number: 数字。
        :param precision: 保留小数点位数。
        :param fallback_failed_prompt: 是否添加本地化失败提示。（默认为False）
        :returns: 本地化后的数字。
        """
        if isint(number):
            number = int(number)
        else:
            return str(number)

        if self.locale in ["zh_cn", "zh_tw"]:
            unit_info = self._get_cjk_unit(Decimal(number))
        else:
            unit_info = self._get_unit(Decimal(number))

        if not unit_info:
            return str(number)

        unit, scale = unit_info
        fmted_num = self._fmt_num(number / scale, precision)
        return self.t_str(f"{fmted_num} {{i18n.unit.{unit}}}", fallback_failed_prompt)

    @staticmethod
    def _get_cjk_unit(number: Decimal) -> Optional[Tuple[int, Decimal]]:
        if number >= Decimal("10e11"):
            return 3, Decimal("10e11")
        if number >= Decimal("10e7"):
            return 2, Decimal("10e7")
        if number >= Decimal("10e3"):
            return 1, Decimal("10e3")
        return None

    @staticmethod
    def _get_unit(number: Decimal) -> Optional[Tuple[int, Decimal]]:
        if number >= Decimal("10e8"):
            return 3, Decimal("10e8")
        if number >= Decimal("10e5"):
            return 2, Decimal("10e5")
        if number >= Decimal("10e2"):
            return 1, Decimal("10e2")
        return None

    @staticmethod
    def _fmt_num(number: Decimal, precision: int) -> str:
        number = number.quantize(
            Decimal(f"1.{"0" * precision}"), rounding=ROUND_HALF_UP
        )
        num_str = f"{number:.{precision}f}".rstrip("0").rstrip(".")
        return num_str if precision > 0 else str(int(number))


locale_loaded_err = load_locale_file()


__all__ = ["Locale", "load_locale_file", "get_available_locales", "locale_loaded_err"]
