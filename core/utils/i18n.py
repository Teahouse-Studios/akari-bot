from typing import List, TypedDict
import ujson as json
import os

# Load all locale files into memory

# We might change this behavior in the future and read them on demand as
# locale files get too large
locale_cache = {}

def load_locale_file():
    locales = os.listdir('./locales')
    for l in locales:
        with open(f'./locales/{l}', 'r', encoding='utf-8') as f:
            locale_cache[l.removesuffix('.json')] = json.load(f)

load_locale_file()

class LocaleFile(TypedDict):
    key: str
    string: str


class Locale:
    def __init__(self, locale: str, fallback_lng: List[str] = ('zh_cn', 'en_us')):
        '''创建一个本地化对象'''

        self.locale = locale
        self.data: LocaleFile = locale_cache[locale]
        self.fallback_lng = fallback_lng

    def __getitem__(self, key: str):
        return self.data[key]

    def __contains__(self, key: str):
        return key in self.data

    def t(self, key: str) -> str:
        '''获取本地化字符串'''
        return self.get_string_with_fallback(key)

    def get_string_with_fallback(self, key: str) -> str:
        value = self.data.get(key, None)
        if value is not None:
            return value # 1. 如果本地化字符串存在，直接返回
        fallback_lng = list(self.fallback_lng)
        fallback_lng.insert(0, self.locale)
        for lng in fallback_lng:
            if lng in locale_cache:
                string = locale_cache[lng].get(key, None)
                if string is not None:
                    return string # 2. 如果在 fallback 语言中本地化字符串存在，直接返回
        return key # 3. 如果在 fallback 语言中本地化字符串不存在，返回 key

__all__ = ['Locale', 'load_locale_file']
