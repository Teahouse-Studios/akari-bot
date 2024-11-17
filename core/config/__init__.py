import os
from typing import Union, Any

from tomlkit import parse as toml_parser, dumps as toml_dumps, TOMLDocument, comment as toml_comment, nl
from loguru import logger
from tomlkit.items import Table

from core.exceptions import ConfigValueError
from core.path import config_path

import core.config.update
from core.utils.i18n import Locale

config_filename = 'config.toml'

cfg_file_path = os.path.join(config_path, config_filename)
old_cfg_file_path = os.path.join(config_path, 'config.cfg')
default_locale = 'zh_cn'


class CFGManager:
    value: Union[None, TOMLDocument] = None
    _ts = None

    @classmethod
    def load(cls):
        try:
            cls.value = toml_parser(open(cfg_file_path, 'r', encoding='utf-8').read())
        except Exception as e:
            raise ConfigValueError(e)
        cls._ts = os.path.getmtime(cfg_file_path)

    @classmethod
    def get(cls, q: str, default: Union[Any, None] = None, cfg_type: Union[type, tuple, None] = None, secret: bool=False, table_name: str=None) -> Any:
        q = q.lower()
        if os.path.getmtime(cfg_file_path) != cls._ts:
            cls.load()

        value = None

        if not table_name:
            for t in cls.value.keys():
                if isinstance(cls.value[t], Table):
                    value = cls.value[t].get(q)
                    if value is not None:
                        break
                else:
                    if t == q:
                        value = cls.value[t]
                        break
        else:
            value = cls.value.get(table_name).get(q)

        if value is None and default is not None:
            logger.warning(f'[Config] Config {q} not found, filled with default value.')
            cls.write(q, default, secret, table_name)

            return default
        if cfg_type:
            if isinstance(cfg_type, type) or isinstance(cfg_type, tuple):
                if isinstance(cfg_type, tuple):
                    cfg_type_str = ', '.join(map(lambda t: t.__name__, cfg_type))
                    if value is not None and not isinstance(value, cfg_type):
                        logger.warning(f'[Config] Config {q} has a wrong type, expected {
                                       cfg_type_str}, got {type(value).__name__}.')
                else:
                    if value is not None and not isinstance(value, cfg_type):
                        logger.warning(
                            f'[Config] Config {q} has a wrong type, expected {
                                cfg_type.__name__}, got {
                                type(value).__name__}.')
            else:
                logger.warning(f'[Config] Invalid cfg_type provided in config {
                               q}. cfg_type should be a type or a tuple of types.')
        elif default:
            if not isinstance(value, type(default)):
                logger.warning(
                    f'[Config] Config {q} has a wrong type, expected {
                        type(default).__name__}, got {
                        type(value).__name__}.')
                return default
        return value

    @classmethod
    def write(cls, q: str, value: Union[Any, None], secret: bool = False, table_name: str = None):
        q = q.lower()
        if os.path.getmtime(cfg_file_path) != cls._ts:
            cls.load()
        found = False
        for t in cls.value.keys():
            if isinstance(cls.value[t], Table):
                if q in cls.value[t]:
                    cls.value[t][q] = value
                    found = True
                    break
            else:
                if t == q:
                    cls.value[t] = value
                    found = True
                    break
        get_locale = Locale(default_locale)
        if not found:
            if isinstance(cls.value, TOMLDocument):
                target = 'cfg'
                if secret:
                    target = 'secret'
                if table_name:
                    target = table_name
                if target in cls.value:
                    cls.value[target].add(nl())
                    qc = 'config.comments.' + q
                    localed_comment = get_locale.t(qc, fallback_failed_prompt=False)
                    if localed_comment != qc:
                        cls.value[target].add(toml_comment(localed_comment))
                    cls.value[target].add(q, value)


        with open(cfg_file_path, 'w', encoding='utf-8') as f:
            f.write(toml_dumps(cls.value))
        cls.load()

    @classmethod
    def delete(cls, q: str) -> bool:
        q = q.lower()
        if os.path.getmtime(cfg_file_path) != cls._ts:
            cls.load()
        value_s = cls.value.get('secret')
        value_n = cls.value.get('cfg')
        if q in value_s:
            del value_s[q]
        elif q in value_n:
            del value_n[q]
        else:
            return False
        cls.value['secret'] = value_s
        cls.value['cfg'] = value_n
        with open(cfg_file_path, 'w', encoding='utf-8') as f:
            f.write(toml_dumps(cls.value))
        cls.load()
        return True

    @classmethod
    def get_url(cls, q: str, default: Union[str, None] = None) -> Union[str, None]:
        q = cls.get(q, default, str)
        if q:
            if q[-1] != '/':
                q += '/'
        return q


CFGManager.load()

class ConfigOption:
    def __init__(self, q: str, default: Union[Any, None] = None, cfg_type: Union[type, tuple, None] = None, secret: bool=False, table_name: str=None):
        self._cfg = CFGManager
        self.q = q
        self.default = default
        self.cfg_type = cfg_type
        self.secret = secret
        self.table_name = table_name


    @property
    def value(self):
        return self._cfg.get(self.q, self.default, self.cfg_type, self.secret, self.table_name)

def config(q: str, default: Union[Any, None] = None, cfg_type: Union[type, tuple, None] = None, secret: bool=False, table_name: str=None) -> Any:
    return ConfigOption(q, default, cfg_type, secret, table_name).value

default_locale = config('default_locale', default_locale, str)
