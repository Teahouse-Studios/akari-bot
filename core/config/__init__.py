import datetime
import os
import re
from time import sleep
from typing import Optional, Union, Any

import orjson as json
from loguru import logger
from tomlkit import parse as toml_parser, dumps as toml_dumps, TOMLDocument, comment as toml_comment, \
    document as toml_document, nl
from tomlkit.exceptions import KeyAlreadyPresent
from tomlkit.items import Table

import core.config.update  # noqa
from core.constants.default import default_locale
from core.constants.exceptions import ConfigValueError, ConfigOperationError
from core.constants.path import config_path
from core.exports import add_export
from core.i18n import Locale


ALLOWED_TYPES = (bool, datetime.datetime, datetime.date, float, int, list, str)


class CFGManager:
    config_path = config_path  # don't change this plzzzzz it will break switch_config_path
    config_file_list = [cfg for cfg in os.listdir(config_path) if cfg.endswith(".toml")]
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
                ConfigOperationError("Operation timeout.")

    @classmethod
    def load(cls):  # Load the config file
        if not cls._load_lock:
            cls._load_lock = True
            try:
                cls.config_file_list = [cfg for cfg in os.listdir(cls.config_path) if cfg.endswith(".toml")]
                for cfg in cls.config_file_list:
                    cfg_name = cfg
                    if cfg_name.endswith(".toml"):
                        cfg_name = cfg_name.removesuffix(".toml")
                    with open(os.path.join(cls.config_path, cfg), "r", encoding="utf-8") as c:
                        cls.values[cfg_name] = toml_parser(c.read())
                    cls._tss[cfg_name] = os.path.getmtime(os.path.join(cls.config_path, cfg))
            except Exception as e:
                raise ConfigValueError(e)
            cls._load_lock = False

    @classmethod
    def save(cls):  # Save the config files
        if not cls._save_lock:
            cls._save_lock = True
            try:
                for cfg in cls.values:
                    cfg_name = cfg
                    if not cfg_name.endswith(".toml"):
                        cfg_name += ".toml"
                    with open(os.path.join(cls.config_path, cfg_name), "w", encoding="utf-8") as f:
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
            for cfg in cls.values:
                cfg_file = cfg
                if not cfg_file.endswith(".toml"):
                    cfg_file += ".toml"
                file_path = os.path.join(cls.config_path, cfg_file)
                if os.path.exists(file_path):
                    if os.path.getmtime(file_path) != cls._tss[cfg]:
                        logger.warning("[Config] Config file has been modified, reloading...")
                        cls.load()
                        break
            cls._watch_lock = False

    @classmethod
    def get(cls,
            q: str,
            default: Union[Any, None] = None,
            cfg_type: Union[type, tuple, None] = None,
            secret: bool = False,
            table_name: Optional[str] = None,
            _global: bool = False,
            _generate: bool = False) -> Any:
        """
        获取配置文件中的配置项。

        :param q: 配置项键名。
        :param default: 默认值。
        :param cfg_type: 配置项类型。
        :param secret: 是否为密钥配置项。（默认为False）
        :param table_name: 配置项表名。

        :return: 配置文件中对应配置项的值。
        """
        cls.watch()
        q = q.lower()
        value = None

        if not table_name:
            if not _global:  # if table_name is not provided, search for the value in config.toml tables
                for t in cls.values["config"].keys():
                    if isinstance(cls.values["config"][t], Table):
                        """
                        [config]
                        foo = bar  <- get the value inside the table
                        """
                        if secret:
                            if "secret" in cls.values["config"]:
                                value = cls.values["config"]["secret"].get(q)
                                if value is not None:
                                    break
                        else:
                            if "config" in cls.values["config"]:
                                value = cls.values["config"]["config"].get(q)
                                if value is not None:
                                    break
                    else:
                        """
                        foo = bar <- if the item is not a table, assume it"s a key-value pair outside the table
                        [config]
                        foo = bar
                        """
                        if t == q:
                            value = cls.values["config"][t]
                            break
            else:  # search for the value in all tables
                found = False
                for t in cls.values:
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
            table_name = table_name.lower()
            # if table_name is provided, write the value to the specified table
            if table_name != "config":
                target = f"{table_name}{"_secret" if secret else ""}"
            else:
                target = "secret" if secret else "config"
            try:
                # if table_name is provided, get for the value in the specified table directly
                value = cls.values[table_name].get(target).get(q)
            except (AttributeError, KeyError):
                pass

        if re.match(r"^<Replace me.*?>$", str(value)):  # if we get a placeholder value, return None
            return None

        if value is None:  # if the value is not found, write the default value to the config file
            if default is not None:
                if isinstance(default, dict):
                    default = json.dumps(default).decode()  # if the default value is dict, convert to json str
                elif not isinstance(default, ALLOWED_TYPES):
                    logger.error(f"[Config] Config {q} has an unsupported default type {type(default).__name__}.")
                    return None
                else:
                    cfg_type = cfg_type if cfg_type else type(default)

            logger.debug(f"[Config] Config {q} not found, filled with default value.")
            cls.write(q, default, cfg_type, secret, table_name, _generate)
            return default

        # if cfg_type provided, start type check
        if cfg_type:
            if isinstance(cfg_type, (type, tuple)):
                if isinstance(cfg_type, tuple) and not all(issubclass(t, ALLOWED_TYPES) for t in cfg_type):
                    logger.error(f"[Config] Config {q} has an unsupported cfg_type {cfg_type}.")
                    return None
                if isinstance(cfg_type, type) and not issubclass(cfg_type, ALLOWED_TYPES):
                    logger.error(f"[Config] Config {q} has an unsupported cfg_type {cfg_type.__name__}.")
                    return None
                # check that value matches cfg_type type
                if value is not None and not isinstance(value, cfg_type):
                    if (float in (cfg_type if isinstance(cfg_type, tuple)
                                  else [cfg_type])) and isinstance(value, int):
                        pass  # allow int as float
                    else:
                        expected_type = ", ".join(map(lambda t: t.__name__, cfg_type)) if isinstance(
                            cfg_type, tuple) else cfg_type.__name__
                        logger.warning(f"[Config] Config {q} has a wrong type, expected {
                            expected_type}, got {type(value).__name__}.")
        elif default is not None and not isinstance(value, type(default)):
            # if cfg_type is not provided but default is given, check that value is consistent with default type
            if not (isinstance(default, float) and isinstance(value, int)):  # allow int as float
                logger.warning(
                    f"[Config] Config {q} has a wrong type, expected {
                        type(default).__name__}, got {
                        type(value).__name__}.")

        return value

    @classmethod
    def write(cls, q: str, value: Union[Any, None], cfg_type: Union[type, tuple, None] = None, secret: bool = False,
              table_name: Optional[str] = None, _generate: bool = False):
        """
        修改配置文件中的配置项。

        :param q: 配置项键名。
        :param value: 修改值。
        :param cfg_type: 配置项类型。
        :param secret: 是否为密钥配置项。（默认为False）
        :param table_name: 配置项表名。
        """
        cls.watch()
        q = q.lower()
        if value is None:
            if _generate:  # if the value is None when generating the config file, fill with a placeholder
                if cfg_type:
                    if isinstance(cfg_type, tuple):
                        cfg_type_str = "(" + ", ".join(map(lambda ty: ty.__name__, cfg_type)) + ")"
                    else:
                        cfg_type_str = cfg_type.__name__
                if cfg_type_str:
                    if cfg_type_str == "list":
                        value = []
                    else:
                        value = f"<Replace me with {cfg_type_str} value>"
                else:
                    value = "<Replace me>"
            else:  # if the value is None, skip to autofill
                logger.debug(f"[Config] Config {q} has no default value, skipped to auto fill.")
                return

        found = False
        if not table_name:  # if table_name is not provided, search for the value in config.toml tables
            for t in cls.values["config"].keys():
                if isinstance(cls.values["config"][t], Table):
                    """
                    [config]
                    foo = bar  <- get the value inside the table
                    """
                    if secret:
                        if "secret" in cls.values["config"]:
                            if q in cls.values["config"]["secret"]:
                                cls.values["config"]["secret"][q] = value
                                found = True
                                break
                    else:
                        if "config" in cls.values["config"]:
                            if q in cls.values["config"]["config"]:
                                cls.values["config"]["config"][q] = value
                                found = True
                                break
                else:
                    """
                    foo = bar <- if the item is not a table, assume it"s a key-value pair outside the table
                    [config]
                    foo = bar
                    """
                    if t == q:
                        cls.values["config"][t] = value
                        found = True
                        break
        else:
            table_name = table_name.lower()
            # if table_name is provided, write the value to the specified table
            if table_name == "secret":
                table_name = "config"
                secret = True
            if table_name.endswith("_secret"):
                table_name = table_name.removesuffix("_secret")
                secret = True

            if table_name != "config":
                target = f"{table_name}{"_secret" if secret else ""}"
            else:
                target = "secret" if secret else "config"
            try:
                # if table_name is provided, get for the value in the specified table directly
                if cls.values[table_name][target][q]:
                    cls.values[table_name][target][q] = value
                    found = True
            except (AttributeError, KeyError):
                pass

        if not found:  # if the value is not found, write the default value to the config file
            if table_name and table_name != "config":  # if table_name is provided, write the value to the specified table
                cfg_name = table_name
                target = f"{table_name}{"_secret" if secret else ""}"
            else:
                cfg_name = "config"
                target = "secret" if secret else "config"

            get_locale = Locale(Config("default_locale", default_locale, str))
            if cfg_name not in cls.values:  # if the target table is not found, create a new table
                cls.values[cfg_name] = toml_document()
                cls.values[cfg_name].add(
                    toml_comment(
                        get_locale.t(
                            "config.header.line.1",
                            fallback_failed_prompt=False)))
                cls.values[cfg_name].add(
                    toml_comment(
                        get_locale.t(
                            "config.header.line.2",
                            fallback_failed_prompt=False)))
                cls.values[cfg_name].add(
                    toml_comment(
                        get_locale.t(
                            "config.header.line.3",
                            fallback_failed_prompt=False)))
            if target not in cls.values[cfg_name]:  # assume the child table name is the same as the parent table name
                if target == "config":
                    table_comment_key = "config.table.config"  # i18n comment
                elif target == "secret":
                    table_comment_key = "config.table.secret"
                elif target.startswith("bot_"):
                    if target.endswith("_secret"):
                        table_comment_key = "config.table.secret_bot"
                    else:
                        table_comment_key = "config.table.config_bot"
                elif target.startswith("module_"):
                    if target.endswith("_secret"):
                        table_comment_key = "config.table.secret_module"
                    else:
                        table_comment_key = "config.table.config_module"
                cls.values[cfg_name].add(nl())
                cls.values[cfg_name].add(target, toml_document())
                cls.values[cfg_name][target].add(toml_comment(get_locale.t(table_comment_key)))

            try:
                cls.values[cfg_name][target].add(q, value)
            except KeyAlreadyPresent:
                cls.values[cfg_name][target][q] = value
            finally:
                qc = f"config.comments.{q}"
                # get the comment for the key from locale
                localed_comment = get_locale.t(qc, fallback_failed_prompt=False)
                if localed_comment != qc:
                    cls.values[cfg_name][target].value.item(q).comment(localed_comment)

        if _generate:
            return

        cls.save()
        cls.load()

    @classmethod
    def delete(cls, q: str, table_name: Optional[str] = None) -> bool:
        """
        删除配置文件中的配置项。

        :param q: 配置项键名。
        :param table_name: 配置项表名。
        """
        cls.watch()
        q = q.lower()
        found = False
        table_name = "config" if not table_name else table_name.lower()
        try:
            for t in cls.values[table_name].keys():
                if isinstance(cls.values[table_name][t], Table):
                    if q in cls.values[table_name][t]:
                        del cls.values[table_name][t][q]
                        found = True
        except (AttributeError, KeyError):
            pass

        if not found:
            return False

        cls.save()
        return True

    @classmethod
    def switch_config_path(cls, path: str):
        cls.config_path = os.path.abspath(path)
        cls._tss = {}
        cls.config_file_list = [cfg for cfg in os.listdir(cls.config_path) if cfg.endswith(".toml")]
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
           _global: bool = False,
           _generate: bool = False) -> Any:
    """
    获取配置文件中的配置项。

    :param q: 配置项键名。
    :param default: 默认值。
    :param cfg_type: 配置项类型。
    :param secret: 是否为密钥配置项。（默认为False）
    :param table_name: 配置项表名。
    :param get_url: 是否为URL配置项。（默认为False）

    :return: 配置文件中对应配置项的值。
    """
    if get_url:
        v = CFGManager.get(q, default, str, secret, table_name, _global, _generate)
        if v:
            if not re.match(r"^[a-zA-Z][a-zA-Z\d+\-.]*://", v):
                v = "http://" + v
            if v[-1] != "/":
                v += "/"
    else:
        v = CFGManager.get(q, default, cfg_type, secret, table_name, _global, _generate)
    return v


add_export(Config)
add_export(CFGManager)
