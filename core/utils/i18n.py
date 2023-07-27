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

class LocaleNode():
    '''本地化树节点'''
    value: str
    childen: dict
    def __init__(self,v:str = None):
        self.value = v
        self.childen = {}
    def qurey_node(self,path:str):
        '''查询本地化树节点'''
        return self._qurey_node(path.split('.'))
    def _qurey_node(self,path:list):
        '''通过路径队列查询本地化树节点'''
        if len(path) == 0:
            return self
        nxt_node = path[0]
        if nxt_node in self.childen.keys():
            return self.childen[nxt_node]._qurey_node(path[1:])
        else:
            return None
    def update_node(self,path:str,write_value:str):
        '''更新本地化树节点'''
        return self._update_node(path.split('.'),write_value)
    def _update_node(self,path:list,write_value:str):
        '''通过路径队列更新本地化树节点'''
        if len(path) == 0:
            self.value = write_value
            return
        nxt_node = path[0]
        if nxt_node not in self.childen.keys():
            self.childen[nxt_node] = LocaleNode()
        self.childen[nxt_node]._update_node(path[1:],write_value)

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
                locale_dict[remove_suffix(l, '.json')] = flatten(json.load(f))
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
                        if remove_suffix(lm, '.json') in locale_dict:
                            locale_dict[remove_suffix(lm, '.json')].update(flatten(json.load(f)))
                        else:
                            locale_dict[remove_suffix(lm, '.json')] = flatten(json.load(f))
                    except Exception as e:
                        err_prompt.append(f'Failed to load {ml}: {e}')
    for lang in locale_dict.keys():
        for k in locale_dict[lang].keys():
            locale_root.update_node(f'{lang}.{k}',locale_dict[lang][k])
    return err_prompt

class Locale:
    def __init__(self, locale: str, fallback_lng=None):
        """创建一个本地化对象"""
        if fallback_lng is None:
            fallback_lng = ['zh_cn', 'zh_tw', 'en_us']
        self.locale = locale
        self.data: LocaleNode = locale_root.qurey_node(locale)
        self.fallback_lng = fallback_lng

    def __getitem__(self, key: str):
        return self.data[key]

    def __contains__(self, key: str):
        return key in self.data

    def t(self, key: str, fallback_failed_prompt=True, *args, **kwargs) -> str:
        '''获取本地化字符串'''
        localized = self.get_string_with_fallback(key, fallback_failed_prompt)
        return Template(localized).safe_substitute(*args, **kwargs)
    
    def get_locale_node(self, path: str):
        '''获取本地化节点'''
        return self.data.qurey_node(path)

    def get_string_with_fallback(self, key: str, fallback_failed_prompt) -> str:
        node = self.data.qurey_node(key)
        if node is not None:
            return node.value  # 1. 如果本地化字符串存在，直接返回
        fallback_lng = list(self.fallback_lng)
        fallback_lng.insert(0, self.locale)
        for lng in fallback_lng:
            if lng in locale_root.childen:
                node = locale_root.qurey_node(lng).qurey_node(key)
                if node is not None:
                    return node.value  # 2. 如果在 fallback 语言中本地化字符串存在，直接返回
        if fallback_failed_prompt:
            return f'{{{key}}}' + self.t("i18n.prompt.fallback.failed", url=Config('bug_report_url'),
                                         fallback_failed_prompt=False)
        else:
            return key
        # 3. 如果在 fallback 语言中本地化字符串不存在，返回 key

def get_available_locales():
    return list(locale_root.childen.keys())

__all__ = ['Locale', 'load_locale_file', 'get_available_locales']