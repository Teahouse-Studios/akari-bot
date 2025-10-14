import glob
import html
import re
import traceback
from collections.abc import MutableMapping
from pathlib import Path
from string import Template
from typing import Any, Dict, List, Optional, Union

import orjson

from core.constants.default import lang_list
from core.constants.path import locales_path, modules_locales_path

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

    locales = [c.name for c in locales_path.iterdir()]
    try:
        for loc in locales:
            with open(locales_path / loc, "rb") as f:
                locale_dict[loc.removesuffix(".json")] = flatten(orjson.loads(f.read()))
    except Exception as e:
        traceback.print_exc()
        err_prompt.append(str(e))

    for modules_locales_file in glob.glob(modules_locales_path):
        if Path(modules_locales_file).is_dir():
            locales_m = [c.name for c in Path(modules_locales_file).iterdir()]
            for lang_file in locales_m:
                lang_file_path = Path(modules_locales_file) / lang_file
                with open(lang_file_path, "rb") as f:
                    try:
                        if lang_file.removesuffix(".json") in locale_dict:
                            locale_dict[lang_file.removesuffix(".json")].update(
                                flatten(orjson.loads(f.read()))
                            )
                        else:
                            locale_dict[lang_file.removesuffix(".json")] = flatten(
                                orjson.loads(f.read())
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
            return f"{{I18N:{key}}}" + self.t(
                "error.i18n.fallback", fallback_failed_prompt=False
            )
        return f"{{I18N:{key}}}"
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

    def t_str(self, text: str, fallback_failed_prompt: bool = False, **kwargs: Dict[str, Any]) -> str:
        """
        替换字符串中的本地化键名。

        :param text: 字符串。
        :param fallback_failed_prompt: 是否添加本地化失败提示。（默认为False）
        :returns: 本地化后的字符串。
        """

        def match_i18ncode(match):
            full = match.group(0)
            key = html.unescape(match.group(1))
            params_str = match.group(2)

            local_kwargs = {}

            if params_str:
                params_str = self.t_str(params_str, fallback_failed_prompt=fallback_failed_prompt)

                param_pairs = re.findall(r"(\w+)=([^,]+)", params_str)
                for k, v in param_pairs:
                    local_kwargs[html.unescape(k)] = html.unescape(v)

            all_kwargs = {**kwargs, **local_kwargs}

            t_value = self.t(key, fallback_failed_prompt=fallback_failed_prompt, **all_kwargs)

            return t_value if isinstance(t_value, str) else full

        prev_text = None
        while prev_text != text:
            prev_text = text
            text = re.sub(r"\{I18N:([^\s,{}]+)(?:,([^\{\}]*))?\}", match_i18ncode, text)

        return text


load_locale_file()

__all__ = ["Locale", "load_locale_file", "get_available_locales"]
