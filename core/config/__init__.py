import os
import re
from time import sleep
from typing import Optional, Union, Any

from loguru import logger
from tomlkit import parse as toml_parser, dumps as toml_dumps, TOMLDocument, comment as toml_comment, \
    document as toml_document, nl
from tomlkit.exceptions import KeyAlreadyPresent
from tomlkit.items import Table

import core.config.update
from core.constants.default import default_locale
from core.constants.exceptions import ConfigValueError, ConfigOperationError
from core.constants.path import config_path
from core.utils.i18n import Locale


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
    def load(cls):  # Load the config file
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
    def save(cls):  # Save the config files
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
    def watch(cls):  # Watch for changes in the config file and reload if necessary
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
    def get(cls,
            q: str,
            default: Union[Any,
                           None] = None,
            cfg_type: Union[type,
                            tuple,
                            None] = None,
            secret: bool = False,
            table_name: Optional[str] = None,
            _generate: bool = False) -> Any:
        cls.watch()
        q = q.lower()
        value = None

        if not table_name:  # if table_name is not provided, search for the value in all tables
            found = False
            for t in cls.values.keys():  # search for the value in all tables
                for tt in cls.values[t].keys():
                    if isinstance(cls.values[t][tt], Table):
                        """
                        [Config]
                        xxx = xxx  <- get the value inside the table
                        """
                        value = cls.values[t][tt].get(q)
                        if value is not None:
                            found = True
                            break
                    else:
                        """
                        xxx = xxx <- if the item is not a table, assume it's a key-value pair outside the table
                        [Config]
                        xxx = xxx
                        """
                        if tt == q:
                            value = cls.values[t][tt]
                            found = True
                            break
                if found:
                    break
        else:
            target = table_name + '_secret' if secret else table_name
            try:
                # if table_name is provided, get for the value in the specified table directly
                value = cls.values[table_name].get(target).get(q)
            except (AttributeError, KeyError):
                pass

        if re.match(r'^<Replace me.*?>$', str(value)):  # if we get a placeholder value, return None
            return None

        if value is None:  # if the value is not found, write the default value to the config file
            logger.debug(f'[Config] Config {q} not found, filled with default value.')
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
                logger.error(f'[Config] Invalid cfg_type provided in config {
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
              table_name: Optional[str] = None, _generate: bool = False):
        cls.watch()
        q = q.lower()
        found = False
        if value is None and _generate:  # if the value is None when generating the config file, fill with a placeholder
            if cfg_type:
                if isinstance(cfg_type, tuple):
                    cfg_type_str = '(' + ', '.join(map(lambda ty: ty.__name__, cfg_type)) + ')'
                else:
                    cfg_type_str = cfg_type.__name__
                value = f"<Replace me with {cfg_type_str} value>"
            else:
                value = "<Replace me>"
        if value is None:  # if the value is None, skip to autofill
            logger.debug(f'[Config] Config {q} has no default value, skipped to auto fill.')
            return

        if not table_name:  # if table_name is not provided, search for the value in all tables
            for t in cls.values.keys():  # search for the value in all tables
                for tt in cls.values[t].keys():
                    if isinstance(cls.values[t][tt], Table):
                        """
                        [Config]
                        xxx = xxx  <- get the value inside the table
                        """
                        if q in cls.values[t][tt]:
                            cls.values[t][tt][q] = value
                            found = True
                            break
                    else:
                        """
                        xxx = xxx <- if the item is not a table, assume it's a key-value pair outside the table
                        [Config]
                        xxx = xxx
                        """
                        if tt == q:
                            cls.values[t][tt] = value
                            found = True
                            break
        if not found:  # if the value is not found, write the default value to the config file
            if table_name:  # if table_name is provided, write the value to the specified table
                cfg_name = table_name
                target = f"{table_name}{'_secret' if secret else ''}"
            else:
                cfg_name = 'config'
                target = 'secret' if secret else 'config'

            get_locale = Locale(Config('default_locale', default_locale, str))
            if cfg_name not in cls.values:  # if the target table is not found, create a new table
                cls.values[cfg_name] = toml_document()
                cls.values[cfg_name].add(
                    toml_comment(
                        get_locale.t(
                            'config.header.line.1',
                            fallback_failed_prompt=False)))
                cls.values[cfg_name].add(
                    toml_comment(
                        get_locale.t(
                            'config.header.line.2',
                            fallback_failed_prompt=False)))
                cls.values[cfg_name].add(
                    toml_comment(
                        get_locale.t(
                            'config.header.line.3',
                            fallback_failed_prompt=False)))
            if target not in cls.values[cfg_name]:  # assume the child table name is the same as the parent table name
                if target == 'config':
                    table_comment_key = 'config.table.config'  # i18n comment
                elif target == 'secret':
                    table_comment_key = 'config.table.secret'
                elif '_secret' in target:
                    table_comment_key = 'config.table.secret_bot'
                else:
                    table_comment_key = 'config.table.config_bot'
                cls.values[cfg_name].add(nl())
                cls.values[cfg_name].add(target, toml_document())
                cls.values[cfg_name][target].add(toml_comment(get_locale.t(table_comment_key)))
            try:
                cls.values[cfg_name][target].add(q, value)
            except KeyAlreadyPresent:
                pass
            qc = f'config.comments.{q}'
            localed_comment = get_locale.t(qc, fallback_failed_prompt=False)  # get the comment for the key from locale
            if localed_comment != qc:
                cls.values[cfg_name][target].value.item(q).comment(localed_comment)

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
            for tt in cls.values[t].keys():
                if isinstance(cls.values[t][tt], Table):
                    if q in cls.values[t][tt]:
                        del cls.values[t][tt][q]
                        found = True
                        break
                else:
                    if cls.values[t][tt] == q:
                        del cls.values[t][tt]
                        found = True
                        break

        if not found:
            return False
        cls.save()
        return True

    @classmethod
    def switch_config_path(cls, path: str):
        config_path = os.path.abspath(path)
        cls._tss = {}
        cls.config_file_list = [cfg for cfg in os.listdir(config_path) if cfg.endswith('.toml')]
        cls.values = {}
        cls._load_lock = False
        cls._save_lock = False
        cls._watch_lock = False
        cls.load()


CFGManager.load()


def Config(q: str,
           default: Union[Any,
                          None] = None,
           cfg_type: Union[type,
                           tuple,
                           None] = None,
           secret: bool = False,
           table_name: Optional[str] = None,
           get_url: bool = False,
           _generate: bool = False):
    if get_url:
        v = CFGManager.get(q, default, str, secret, table_name=table_name, _generate=_generate)
        if v:
            if v[-1] != '/':
                v += '/'
    else:
        v = CFGManager.get(q, default, cfg_type, secret, table_name, _generate)
    return v
