import os
from collections.abc import MutableMapping
from string import Template
from typing import TypedDict, Dict, Any

import ujson as json

from config import Config
from .text import remove_suffix

# Load all locale files into memory

# We might change this behavior in the future and read them on demand as
# locale files get too large
locale_cache = {}


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
    err_prompt = []
    locales_path = os.path.abspath('./locales')
    locales = os.listdir(locales_path)
    try:
        for l in locales:
            with open(f'{locales_path}/{l}', 'r', encoding='utf-8') as f:
                locale_cache[remove_suffix(l, '.json')] = flatten(json.load(f))
    except Exception as e:
        err_prompt.append(str(e))
    modules_path = os.path.abspath('./modules')
    for m in os.listdir(modules_path):
        if os.path.isdir(f'{modules_path}/{m}/locales'):
            locales_m = os.listdir(f'{modules_path}/{m}/locales')
            for lm in locales_m:
                ml = f'{modules_path}/{m}/locales/{lm}'
                with open(ml, 'r', encoding='utf-8') as f:
                    try:
                        if remove_suffix(lm, '.json') in locale_cache:
                            locale_cache[remove_suffix(lm, '.json')].update(flatten(json.load(f)))
                        else:
                            locale_cache[remove_suffix(lm, '.json')] = flatten(json.load(f))
                    except Exception as e:
                        err_prompt.append(f'Failed to load {ml}: {e}')

    return err_prompt


class LocaleFile(TypedDict):
    key: str
    string: str


class Locale:
    def __init__(self, locale: str, fallback_lng=None):
        """创建一个本地化对象"""

        if fallback_lng is None:
            fallback_lng = ['zh_cn', 'zh_tw', 'en_us']
        self.locale = locale
        self.data: LocaleFile = locale_cache[locale]
        self.fallback_lng = fallback_lng

    def __getitem__(self, key: str):
        return self.data[key]

    def __contains__(self, key: str):
        return key in self.data

    def t(self, key: str, fallback_failed_prompt=True, *args, **kwargs) -> str:
        '''获取本地化字符串'''
        localized = self.get_string_with_fallback(key, fallback_failed_prompt)
        return Template(localized).safe_substitute(*args, **kwargs)

    def get_string_with_fallback(self, key: str, fallback_failed_prompt) -> str:
        value = self.data.get(key, None)
        if value is not None:
            return value  # 1. 如果本地化字符串存在，直接返回
        fallback_lng = list(self.fallback_lng)
        fallback_lng.insert(0, self.locale)
        for lng in fallback_lng:
            if lng in locale_cache:
                string = locale_cache[lng].get(key, None)
                if string is not None:
                    return string  # 2. 如果在 fallback 语言中本地化字符串存在，直接返回
        if fallback_failed_prompt:
            return f'{{{key}}}' + self.t("i18n.prompt.fallback.failed", url=Config('bug_report_url'),
                                         fallback_failed_prompt=False)
        else:
            return key
        # 3. 如果在 fallback 语言中本地化字符串不存在，返回 key


def get_available_locales():
    return list(locale_cache.keys())


__all__ = ['Locale', 'load_locale_file', 'get_available_locales']
