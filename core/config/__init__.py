import os
import re
from time import sleep
from typing import Union, Any

from tomlkit import parse as toml_parser, dumps as toml_dumps, TOMLDocument, comment as toml_comment, \
    document as toml_document, nl
from loguru import logger
from tomlkit.items import Table

from core.constants.exceptions import ConfigValueError, ConfigOperationError

import core.config.update
from core.utils.i18n import Locale

from core.constants import default_locale, config_path


class CFGManager:
    config_file_list = [cfg for cfg in os.listdir(config_path) if cfg.endswith('.toml')]
    values: dict[str, TOMLDocument] = {}
    _tss: dict[str, float] = {}
    _load_lock = False
    _save_lock = False
    _watch_lock = False

    @classmethod
    def wait(cls, _lock):
        count = 0
        while _lock:
            count += 1
            sleep(1)
            if count > 5:
                ConfigOperationError('Operation timeout.')

    @classmethod
    def load(cls):
        if not cls._load_lock:
            cls._load_lock = True
            try:
                cls.config_file_list = [cfg for cfg in os.listdir(config_path) if cfg.endswith('.toml')]
                for cfg in cls.config_file_list:
                    cfg_name = cfg
                    if cfg_name.endswith('.toml'):
                        cfg_name = cfg_name.removesuffix('.toml')
                    cls.values[cfg_name] = toml_parser(
                        open(
                            os.path.join(
                                config_path,
                                cfg),
                            'r',
                            encoding='utf-8').read())
                    cls._tss[cfg_name] = os.path.getmtime(os.path.join(config_path, cfg))
            except Exception as e:
                raise ConfigValueError(e)
            cls._load_lock = False

    @classmethod
    def save(cls):
        if not cls._save_lock:
            cls._save_lock = True
            try:
                for cfg in cls.values.keys():
                    cfg_name = cfg
                    if not cfg_name.endswith('.toml'):
                        cfg_name += '.toml'
                    with open(os.path.join(config_path, cfg_name), 'w', encoding='utf-8') as f:
                        f.write(toml_dumps(cls.values[cfg], sort_keys=True))
            except Exception as e:
                raise ConfigValueError(e)
            cls._save_lock = False
        else:
            cls.wait(cls._save_lock)
            cls.save()

    @classmethod
    def watch(cls):
        if not cls._watch_lock:
            cls._watch_lock = True
            for cfg in cls.values.keys():
                cfg_file = cfg
                if not cfg_file.endswith('.toml'):
                    cfg_file += '.toml'
                file_path = os.path.join(config_path, cfg_file)
                if os.path.exists(file_path):
                    if os.path.getmtime(file_path) != cls._tss[cfg]:
                        logger.warning(f'[Config] Config file has been modified, reloading...')
                        cls.load()
                        break
            cls._watch_lock = False

    @classmethod
    def get(cls, q: str, default: Union[Any, None] = None, cfg_type: Union[type,
            tuple, None] = None, secret: bool = False, table_name: str = None, _generate: bool = False) -> Any:
        cls.watch()
        q = q.lower()
        value = None

        if not table_name:
            found = False
            for t in cls.values.keys():
                for tt in cls.values[t].keys():
                    if isinstance(cls.values[t][tt], Table):
                        value = cls.values[t][tt].get(q)
                        if value is not None:
                            found = True
                            break
                    else:
                        if tt == q:
                            value = cls.values[t][tt]
                            found = True
                            break
                if found:
                    break
        else:
            try:
                value = cls.values[table_name].get(table_name).get(q)
            except (AttributeError, KeyError):
                pass

        if re.match(r'^<Replace me.*?>$', str(value)):
            return None

        if value is None:
            logger.warning(f'[Config] Config {q} not found, filled with default value.')
            cls.write(q, default, cfg_type, secret, table_name, _generate)

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
    def write(cls, q: str, value: Union[Any, None], cfg_type: Union[type, tuple, None] = None, secret: bool = False,
              table_name: str = None, _generate: bool = False):
        cls.watch()
        q = q.lower()
        found = False
        if value is None:
            if cfg_type:
                value = f"<Replace me with a {str(cfg_type)} value>"
            else:
                value = "<Replace me>"
        if not table_name:
            for t in cls.values.keys():
                for tt in cls.values[t].keys():
                    if isinstance(cls.values[t][tt], Table):
                        if q in cls.values[t][tt]:
                            cls.values[t][tt][q] = value
                            found = True
                            break
                    else:
                        if tt == q:
                            cls.values[t][tt] = value
                            found = True
                            break
        if not found:
            target = 'config'
            if secret:
                target = 'secret'
            if table_name:
                target = table_name
            if target not in cls.values:
                cls.values[target] = toml_document()
            if target not in cls.values[target]:
                if target == 'config':
                    table_comment_key = 'config.table.config'
                elif target == 'secret':
                    table_comment_key = 'config.table.secret'
                elif 'secret' in target:
                    table_comment_key = 'config.table.secret_bot'
                else:
                    table_comment_key = 'config.table.config_bot'
                get_locale = Locale(Config('default_locale', default_locale, str))
                cls.values[target].add(toml_comment(get_locale.t('config.header.line.1')))
                cls.values[target].add(toml_comment((get_locale.t('config.header.line.2'))))
                cls.values[target].add(toml_comment((get_locale.t('config.header.line.3'))))
                cls.values[target].add(nl())
                cls.values[target].add(toml_comment(get_locale.t(table_comment_key)))
                cls.values[target].add(target, toml_document())

            cls.values[target][target].add(q, value)
            qc = 'config.comments.' + q
            get_locale = Locale(Config('default_locale', default_locale, str))
            localed_comment = get_locale.t(qc, fallback_failed_prompt=False)
            if localed_comment != qc:
                cls.values[target][target].value.item(q).comment(localed_comment)

        if _generate:
            return

        cls.save()
        cls.load()

    @classmethod
    def delete(cls, q: str) -> bool:
        cls.watch()
        q = q.lower()
        found = False
        for t in cls.values.keys():
            if isinstance(cls.values[t][t], Table):
                if q in cls.values[t][t]:
                    del cls.values[t][t][q]
                    found = True
                    break
            else:
                if cls.values[t][t] == q:
                    del cls.values[t][t]
                    found = True
                    break

        if not found:
            return False
        cls.save()
        return True

    @classmethod
    def get_url(cls, q: str, default: Union[str, None] = None) -> Union[str, None]:
        q = cls.get(q, default, str)
        if q:
            if q[-1] != '/':
                q += '/'
        return q


CFGManager.load()
Config = CFGManager.get
