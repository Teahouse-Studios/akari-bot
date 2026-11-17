"""配置项语义层。"""

import multiprocessing
import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import orjson
from loguru import logger
from tomlkit.items import Table

from core.builtins.config.generator import repair_i18n_comments, resolve_generated_value, write_missing_key
from core.builtins.config.interface import ALLOWED_TYPES
from core.builtins.config.store import TomlStore
from core.constants.exceptions import ConfigNotInitializedError, ConfigOperationError
from core.constants.path import CONFIG_READONLY_ENV, config_path as default_config_path

# 守护进程在 spawn 子进程之前置位，spawn 会继承环境。
CONFIG_READONLY = bool(os.environ.get(CONFIG_READONLY_ENV))


def normalize_table(table_name: str | None, secret: bool) -> tuple[str | None, bool]:
    """将表名归一化为配置文件名与是否为密钥表的组合。

    :param table_name: 调用方传入的表名。
    :param secret: 调用方传入的密钥标志。
    :return: (归一化后的表名, 归一化后的密钥标志)。
    """
    if not table_name:
        return table_name, secret
    table_name = table_name.lower()
    if table_name == "secret":
        return "config", True
    if table_name.endswith("_secret"):
        return table_name.removesuffix("_secret"), True
    return table_name, secret


class ConfigManager:
    """配置项的读取与写入入口。"""

    _store = TomlStore(default_config_path)
    # 与 _store.path 同步，只在 switch_config_path() 中写入。
    config_path = default_config_path

    # 运行期只读状态统一取自该类属性，便于测试覆盖。
    readonly: bool = CONFIG_READONLY
    _allow_write_depth = 0

    @classmethod
    def is_loaded(cls) -> bool:
        """配置是否已加载。

        :return: 至少有一份配置文件已读入内存时为 True。
        """
        return bool(cls._store.values)

    @classmethod
    def _require_loaded(cls) -> None:
        if cls._store.values:
            return
        process_name = multiprocessing.current_process().name
        raise ConfigNotInitializedError(
            f"Config is not initialized in process {process_name!r}. Call bootstrap_config() first."
        )

    @classmethod
    def iter_tables(cls) -> Iterator[str]:
        """遍历已加载的配置文件名（不含扩展名）。

        :return: 配置文件名的迭代器。
        """
        return iter(cls._store.values)

    @classmethod
    def document(cls, name: str):
        """取配置文件名对应的 TOML 文档。

        :param name: 配置文件名，不含扩展名。
        :return: TOML 文档；文件不存在时为 None。
        """
        return cls._store.values.get(name)

    @classmethod
    def iter_secret_values(cls) -> Iterator[Any]:
        """遍历全部密钥表中的取值。

        :return: 密钥取值的迭代器。
        """
        for document in cls._store.values.values():
            for name, table in document.items():
                if not isinstance(table, Table):
                    continue
                if name == "secret" or name.endswith("_secret"):
                    yield from table.values()

    @classmethod
    def bot_enable(cls, name: str) -> bool | None:
        """读取平台配置中的 enable 开关。

        :param name: 平台名，与 ``bots/`` 下的目录名一致。
        :return: 开关取值；对应的配置文件或 enable 键不存在时为 None。
        """
        document = cls._store.values.get(f"bot_{name}")
        if not document:
            return None
        table = document.get(f"bot_{name}")
        if not isinstance(table, Table) or "enable" not in table:
            return None
        return bool(table["enable"])

    @classmethod
    def load(cls) -> None:
        """从磁盘重新加载全部配置文件。"""
        cls._store.load()

    @classmethod
    def save(cls) -> None:
        """将内存中的配置写回磁盘。"""
        cls._require_loaded()
        cls._ensure_writable()
        cls._store.save()

    @classmethod
    def watch(cls) -> None:
        """按最小间隔检查磁盘上的配置改动并热重载。"""
        cls._store.watch()

    @classmethod
    def switch_config_path(cls, path: "Path") -> None:
        """切换配置目录并立即重新加载。

        :param path: 新的配置目录。
        """
        cls._store.switch_path(path)
        cls.config_path = cls._store.path

    @classmethod
    @contextmanager
    def _writable(cls):
        cls._allow_write_depth += 1
        try:
            yield
        finally:
            cls._allow_write_depth -= 1

    @classmethod
    def _ensure_writable(cls, q: str | None = None, table_name: str | None = None, secret: bool = False):
        if not cls.readonly or cls._allow_write_depth:
            return
        process_name = multiprocessing.current_process().name
        if q:
            target = table_name or ("secret" if secret else "config")
            detail = f'write "{q}" to table "{target}"'
        else:
            detail = "save config files"
        raise ConfigOperationError(
            f"Config is read-only in process {process_name!r}, cannot {detail}. "
            "Missing keys must be generated in pre_init."
        )

    @classmethod
    def has(cls, q: str, secret: bool = False, table_name: str | None = None) -> bool:
        """
        判断配置项是否已存在。

        :param q: 配置项键名。
        :param secret: 是否为密钥配置项。（默认为False）
        :param table_name: 配置项表名。
        :return: 配置项是否已存在。
        """
        table_name, secret = normalize_table(table_name, secret)

        if not table_name or table_name == "config":
            cfg_name, target = "config", "secret" if secret else "config"
        else:
            cfg_name = table_name
            target = f"{table_name}{'_secret' if secret else ''}"

        document = cls._store.values.get(cfg_name)
        if not document:
            return False
        if q in document and not isinstance(document[q], Table):
            return True
        table = document.get(target)
        return bool(table) and q in table

    @classmethod
    def repair_i18n_comments(cls) -> int:
        """翻译配置中遗留的 ``{I18N:key}`` 注释标记。

        :return: 被替换或清空的注释数量。
        """
        cls._require_loaded()
        cls._ensure_writable()
        return repair_i18n_comments(cls._store.values)

    @classmethod
    def get(
        cls,
        q: str,
        default: Any | None = None,
        cfg_type: type | tuple | None = None,
        secret: bool = False,
        table_name: str | None = None,
        _global: bool = False,
        _generate: bool = False,
        standalone_comment_keys: tuple[str, ...] = (),
    ) -> Any:
        """
        获取配置文件中的配置项。

        :param q: 配置项键名。
        :param default: 默认值。
        :param cfg_type: 配置项类型。
        :param secret: 是否为密钥配置项。（默认为False）
        :param table_name: 配置项表名。
        :param _global: 内部变量，是否在所有表中查找配置项。（默认为False）
        :param _generate: 内部变量，生成配置文件时使用。（默认为False）
        :param standalone_comment_keys: 生成字段前独立注释块所使用的 i18n 键

        :return: 配置文件中对应配置项的值。
        """
        cls._require_loaded()
        cls.watch()
        q = q.lower()
        value = None
        values = cls._store.values

        if not table_name:
            if not _global:
                for t in values["config"].keys():
                    if isinstance(values["config"][t], Table):
                        if secret:
                            if "secret" in values["config"]:
                                value = values["config"]["secret"].get(q)
                                if value is not None:
                                    break
                        else:
                            if "config" in values["config"]:
                                value = values["config"]["config"].get(q)
                                if value is not None:
                                    break
                    else:
                        if t == q:
                            value = values["config"][t]
                            break
            else:
                found = False
                for t in values:
                    for tt in values[t].keys():
                        if isinstance(values[t][tt], Table):
                            value = values[t][tt].get(q)
                            if value is not None:
                                found = True
                                break
                        else:
                            if tt == q:
                                value = values[t][tt]
                                found = True
                                break
                    if found:
                        break
        else:
            table_name, secret = normalize_table(table_name, secret)

            if table_name != "config":
                target = f"{table_name}{'_secret' if secret else ''}"
            else:
                target = "secret" if secret else "config"
            try:
                value = values[table_name].get(target).get(q)
            except (AttributeError, KeyError):
                pass

        if re.match(r"^<Replace me.*?>$", str(value)):
            return None

        if value is None:
            if default is not None:
                if isinstance(default, dict):
                    default = orjson.dumps(default).decode()
                elif isinstance(default, tuple):
                    default = list(default)
                    cfg_type = cfg_type if cfg_type else list
                elif not isinstance(default, ALLOWED_TYPES):
                    logger.error(f"[Config] Config {q} has an unsupported default type {type(default).__name__}.")
                    return None
                else:
                    cfg_type = cfg_type if cfg_type else type(default)

            cls.write(q, default, cfg_type, secret, table_name, _generate, standalone_comment_keys)
            return default

        if cfg_type:
            if isinstance(cfg_type, (type, tuple)):
                if isinstance(cfg_type, tuple) and not all(issubclass(t, ALLOWED_TYPES) for t in cfg_type):
                    logger.error(f"[Config] Config {q} has an unsupported cfg_type {cfg_type}.")
                    return None
                if isinstance(cfg_type, type) and not issubclass(cfg_type, ALLOWED_TYPES):
                    logger.error(f"[Config] Config {q} has an unsupported cfg_type {cfg_type.__name__}.")
                    return None
                if value is not None and not isinstance(value, cfg_type):
                    if list in (cfg_type if isinstance(cfg_type, tuple) else [cfg_type]) and isinstance(value, tuple):
                        value = list(value)
                    if (float in (cfg_type if isinstance(cfg_type, tuple) else [cfg_type])) and isinstance(value, int):
                        pass
                    else:
                        expected_type = (
                            ", ".join(map(lambda t: t.__name__, cfg_type))
                            if isinstance(cfg_type, tuple)
                            else cfg_type.__name__
                        )
                        logger.warning(
                            f"[Config] Config {q} has a wrong type, expected {expected_type}, got {
                                type(value).__name__
                            }."
                        )
        elif default is not None and not isinstance(value, type(default)):
            if not (isinstance(default, float) and isinstance(value, int)):
                logger.warning(
                    f"[Config] Config {q} has a wrong type, expected {type(default).__name__}, got {
                        type(value).__name__
                    }."
                )

        return value

    @classmethod
    def _set_existing(cls, q: str, value: Any, secret: bool, table_name: str | None) -> bool:
        values = cls._store.values
        if not table_name:
            for t in values["config"].keys():
                if isinstance(values["config"][t], Table):
                    if secret:
                        if "secret" in values["config"]:
                            if q in values["config"]["secret"]:
                                values["config"]["secret"][q] = value
                                return True
                    else:
                        if "config" in values["config"]:
                            if q in values["config"]["config"]:
                                values["config"]["config"][q] = value
                                return True
                else:
                    if t == q:
                        values["config"][t] = value
                        return True
            return False

        if table_name != "config":
            target = f"{table_name}{'_secret' if secret else ''}"
        else:
            target = "secret" if secret else "config"
        try:
            if values[table_name][target][q]:
                values[table_name][target][q] = value
                return True
        except (AttributeError, KeyError):
            pass
        return False

    @classmethod
    def write(
        cls,
        q: str,
        value: Any | None,
        cfg_type: type | tuple | None = None,
        secret: bool = False,
        table_name: str | None = None,
        _generate: bool = False,
        standalone_comment_keys: tuple[str, ...] = (),
    ):
        """
        修改配置文件中的配置项。

        :param q: 配置项键名。
        :param value: 修改值。
        :param cfg_type: 配置项类型。
        :param secret: 是否为密钥配置项。（默认为False）
        :param table_name: 配置项表名。
        :param standalone_comment_keys: 生成字段前独立注释块所使用的 i18n 键。
        """
        cls._require_loaded()
        cls.watch()
        q = q.lower()
        if value is None:
            if _generate:
                logger.debug(f"[Config] Config {q} not found, filled with default value.")
                value = resolve_generated_value(value, cfg_type)
            else:
                logger.debug(f"[Config] Config {q} has no default value, skipped to auto fill.")
                return

        # 守卫置于此处而非方法体最前：无默认值的读取以 value=None 进入上方分支并提前返回，
        # 不涉及写入，不应抛出异常。
        cls._ensure_writable(q, table_name, secret)
        if table_name:
            table_name, secret = normalize_table(table_name, secret)

        # 「重新加载 → 修改 → 保存」须在同一个临界区内完整完成。
        # 否则本进程会以过时的内存副本整体覆盖磁盘，致使其它进程期间写入的配置项丢失。
        with cls._store.exclusive():
            if not _generate:
                cls._store.load()

            if not cls._set_existing(q, value, secret, table_name):
                write_missing_key(
                    cls._store.values,
                    q=q,
                    value=value,
                    secret=secret,
                    table_name=table_name,
                    standalone_comment_keys=standalone_comment_keys,
                )

            if _generate:
                return

            cls._store.save()
            cls._store.load()

    @classmethod
    def delete(cls, q: str, table_name: str | None = None) -> bool:
        """
        删除配置文件中的配置项。

        :param q: 配置项键名。
        :param table_name: 配置项表名。
        :return: 配置项是否被删除。
        """
        cls._require_loaded()
        cls.watch()
        q = q.lower()
        cls._ensure_writable(q, table_name)
        found = False
        table_name = "config" if not table_name else table_name.lower()
        try:
            for t in cls._store.values[table_name].keys():
                if isinstance(cls._store.values[table_name][t], Table):
                    if q in cls._store.values[table_name][t]:
                        del cls._store.values[table_name][t][q]
                        found = True
        except (AttributeError, KeyError):
            pass

        if not found:
            return False

        cls.save()
        return True

    @classmethod
    def edit_write(
        cls,
        q: str,
        value: Any | None,
        cfg_type: type | tuple | None = None,
        secret: bool = False,
        table_name: str | None = None,
    ):
        """授权写入，供交互式编辑命令与启动期的密钥自举使用。

        :param q: 配置项键名。
        :param value: 修改值。
        :param cfg_type: 配置项类型。
        :param secret: 是否为密钥配置项。（默认为False）
        :param table_name: 配置项表名。
        """
        with cls._writable():
            cls.write(q, value, cfg_type, secret, table_name)

    @classmethod
    def edit_delete(cls, q: str, table_name: str | None = None) -> bool:
        """授权删除，供交互式编辑命令使用。

        :param q: 配置项键名。
        :param table_name: 配置项表名。
        :return: 配置项是否被删除。
        """
        with cls._writable():
            return cls.delete(q, table_name)


CFGManager = ConfigManager

__all__ = ["CFGManager", "ConfigManager", "normalize_table"]
