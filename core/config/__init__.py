import datetime
import os
import re
import time
from contextlib import contextmanager
from pathlib import Path
from time import sleep
from typing import Any

import orjson
from loguru import logger
from tomlkit import (
    parse as toml_parser,
    dumps as toml_dumps,
    TOMLDocument,
    comment as toml_comment,
    document as toml_document,
    nl,
)
from tomlkit.exceptions import KeyAlreadyPresent
from tomlkit.items import Table

import core.config.update  # noqa
from core.constants.default import default_locale
from core.constants.exceptions import ConfigValueError, ConfigOperationError
from core.constants.path import config_path as default_config_path
from core.exports import add_export
from core.i18n import Locale

ALLOWED_TYPES = (bool, datetime.datetime, datetime.date, float, int, list, str)


class CFGManager:
    config_path = default_config_path  # don't change this plzzzzz it will break switch_config_path
    config_file_list = [cfg.name for cfg in config_path.glob("*.toml")]
    values: dict[str, TOMLDocument] = {}
    _tss: dict[str, float] = {}
    _watch_lock = False
    _lock_depth = 0

    # 等待进入临界区的上限（秒）
    LOCK_TIMEOUT = 10.0
    # 锁文件被判定为陈旧的时长（秒）。该值须显著大于一次正常读写的耗时，
    # 否则会回收仍处于临界区内的进程所持有的锁，导致两个进程同时改写而使配置项互相覆盖
    LOCK_STALE = 60.0

    @classmethod
    @contextmanager
    def _exclusive(cls):
        """
        以配置目录下的锁文件在进程间互斥，可重入。

        守护进程为每个平台各启动一个子进程，另有一个 server 进程，它们均会读写同一批配置文件，
        而类属性形式的锁在每个进程中各有一份，无法约束跨进程的并发写入。此处改用锁文件，
        使同一时刻仅有一个进程处于读写配置的临界区内。

        可重入是必要的：一次改写须在同一个临界区内完成「重新加载 → 修改 → 保存」，
        否则本进程会以过时的内存副本整体覆盖磁盘，致使其它进程期间写入的配置项丢失。
        """
        if cls._lock_depth:
            cls._lock_depth += 1
            try:
                yield
            finally:
                cls._lock_depth -= 1
            return

        lock_path = cls.config_path / ".config.lock"
        deadline = time.monotonic() + cls.LOCK_TIMEOUT
        fd = None
        while fd is None:
            try:
                fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                # 持锁进程若被强制结束会遗留锁文件，超过时限即判定为陈旧锁并予以回收。
                try:
                    if time.time() - lock_path.stat().st_mtime > cls.LOCK_STALE:
                        lock_path.unlink(missing_ok=True)
                        continue
                except OSError:
                    pass
                if time.monotonic() > deadline:
                    raise ConfigOperationError("Operation timeout.")
                sleep(0.05)
        cls._lock_depth = 1
        try:
            yield
        finally:
            cls._lock_depth = 0
            os.close(fd)
            lock_path.unlink(missing_ok=True)

    @classmethod
    def load(cls):  # Load the config file
        with cls._exclusive():
            try:
                cls.config_file_list = [cfg.name for cfg in cls.config_path.glob("*.toml")]
                for cfg in cls.config_file_list:
                    cfg_name = cfg
                    if cfg_name.endswith(".toml"):
                        cfg_name = cfg_name.removesuffix(".toml")
                    with open(cls.config_path / cfg, "r", encoding="utf-8") as c:
                        parsed = toml_parser(c.read())
                    # 空 TOML 属于合法输入，解析不会报错。若磁盘上的文件已被清空而内存中仍有内容，
                    # 直接覆盖会在下一次保存时将该空状态写回磁盘，配置即永久丢失。
                    if not parsed and cls.values.get(cfg_name):
                        logger.error(f"[Config] Config file {cfg} is empty, keeping the loaded values.")
                        continue
                    cls.values[cfg_name] = parsed
                    cls._tss[cfg_name] = (cls.config_path / cfg).stat().st_mtime
            except Exception as e:
                raise ConfigValueError(e)

    @classmethod
    def save(cls):  # Save the config files
        with cls._exclusive():
            try:
                for cfg in cls.values:
                    cfg_name = cfg
                    if not cfg_name.endswith(".toml"):
                        cfg_name += ".toml"
                    file_path = cls.config_path / cfg_name
                    content = toml_dumps(cls.values[cfg], sort_keys=True)
                    # 仅写入内容确有变化的文件。一次改写通常只涉及一个配置项，
                    # 若重写全部二十余个文件，既会延长临界区，也会触发其它进程的无谓重新加载。
                    if file_path.exists() and file_path.read_text(encoding="utf-8") == content:
                        continue
                    cls._atomic_write(file_path, content)
            except Exception as e:
                raise ConfigValueError(e)

    @staticmethod
    def _atomic_write(path: Path, content: str):
        """
        原子地写入配置文件。

        以 ``"w"`` 直接打开会立即截断原文件，此后进程若被强制结束（守护进程重启子进程所用的
        正是 SIGKILL），磁盘上将只剩一个空文件；而空 TOML 解析不会报错，下次加载即静默丢失全部配置。
        因此先写入同目录下的临时文件，再由 ``os.replace()`` 原子替换。

        :param path: 目标文件路径。
        :param content: 文件内容。
        """
        tmp_path = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, path)
        finally:
            tmp_path.unlink(missing_ok=True)

    @classmethod
    def watch(cls):  # Watch for changes in the config file and reload if necessary
        if cls._watch_lock:
            return
        cls._watch_lock = True
        try:
            for cfg in cls.values:
                cfg_file = cfg
                if not cfg_file.endswith(".toml"):
                    cfg_file += ".toml"
                file_path = cls.config_path / cfg_file
                if file_path.exists():
                    if file_path.stat().st_mtime != cls._tss.get(cfg):
                        logger.warning("[Config] Config file has been modified, reloading...")
                        cls.load()
                        break
        finally:
            # 若不置于 finally 中，一旦加载抛出异常，此后 watch() 将永久空转，磁盘上的改动无法再被读取。
            cls._watch_lock = False

    @classmethod
    def has(cls, q: str, secret: bool = False, table_name: str | None = None) -> bool:
        """
        判断配置项是否已存在。

        :param q: 配置项键名。
        :param secret: 是否为密钥配置项。（默认为False）
        :param table_name: 配置项表名。
        :return: 配置项是否已存在。
        """
        q = q.lower()
        if table_name:
            table_name = table_name.lower()
            if table_name == "secret":
                table_name, secret = "config", True
            if table_name.endswith("_secret"):
                table_name, secret = table_name.removesuffix("_secret"), True

        if not table_name or table_name == "config":
            cfg_name, target = "config", "secret" if secret else "config"
        else:
            cfg_name = table_name
            target = f"{table_name}{'_secret' if secret else ''}"

        document = cls.values.get(cfg_name)
        if not document:
            return False
        # 表外的顶层键值对，例如 default_locale。
        if q in document and not isinstance(document[q], Table):
            return True
        table = document.get(target)
        return bool(table) and q in table

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
                        foo = bar <- if the item is not a table, assume it is a key-value pair outside the table
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
                target = f"{table_name}{'_secret' if secret else ''}"
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
                    default = orjson.dumps(default).decode()  # if the default value is dict, convert to json str
                elif isinstance(default, tuple):  # if the default value is tuple, convert to list
                    default = list(default)
                    cfg_type = cfg_type if cfg_type else list
                elif not isinstance(default, ALLOWED_TYPES):
                    logger.error(f"[Config] Config {q} has an unsupported default type {type(default).__name__}.")
                    return None
                else:
                    cfg_type = cfg_type if cfg_type else type(default)

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
                    if list in (cfg_type if isinstance(cfg_type, tuple) else [cfg_type]) and isinstance(value, tuple):
                        value = list(value)  # allow tuple as list
                    if (float in (cfg_type if isinstance(cfg_type, tuple) else [cfg_type])) and isinstance(value, int):
                        pass  # allow int as float
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
            # if cfg_type is not provided but default is given, check that value is consistent with default type
            if not (isinstance(default, float) and isinstance(value, int)):  # allow int as float
                logger.warning(
                    f"[Config] Config {q} has a wrong type, expected {type(default).__name__}, got {
                        type(value).__name__
                    }."
                )

        return value

    @classmethod
    def write(
        cls,
        q: str,
        value: Any | None,
        cfg_type: type | tuple | None = None,
        secret: bool = False,
        table_name: str | None = None,
        _generate: bool = False,
    ):
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
                logger.debug(f"[Config] Config {q} not found, filled with default value.")
                cfg_type_str = None
                if cfg_type:
                    if isinstance(cfg_type, tuple):
                        cfg_type_str = "(" + ", ".join(map(lambda ty: ty.__name__, cfg_type)) + ")"
                    else:
                        # 联合类型等对象不具有 __name__，无法取得时退回通用占位符，避免生成注释的过程中断
                        cfg_type_str = getattr(cfg_type, "__name__", None)
                # 生成模式下无论类型是否可用，均须写入占位符：
                # 若保留 None，下方的写入不会建立该配置项，随后读取其注释时将抛出 NonExistentKey
                if cfg_type_str == "list":
                    value = []
                elif cfg_type_str:
                    value = f"<Replace me with {cfg_type_str} value>"
                else:
                    value = "<Replace me>"
            else:  # if the value is None, skip to autofill
                logger.debug(f"[Config] Config {q} has no default value, skipped to auto fill.")
                return

        # 「重新加载 → 修改 → 保存」须在同一个临界区内完整完成。
        # 否则本进程会以过时的内存副本整体覆盖磁盘，致使其它进程期间写入的配置项丢失。
        with cls._exclusive():
            if not _generate:
                cls.load()

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
                    target = f"{table_name}{'_secret' if secret else ''}"
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
                if (
                    table_name and table_name != "config"
                ):  # if table_name is provided, write the value to the specified table
                    cfg_name = table_name
                    target = f"{table_name}{'_secret' if secret else ''}"
                else:
                    cfg_name = "config"
                    target = "secret" if secret else "config"

                # 此处不可再经由 Config() 获取：配置文件一旦损坏，default_locale 同样无法取得，
                # 将再次进入本分支，形成无限递归直至栈溢出。改为直接读取顶层键，取不到则使用默认值。
                get_locale = Locale(cls.values.get("config", {}).get("default_locale") or default_locale)
                if cfg_name not in cls.values:  # if the target table is not found, create a new table
                    cls.values[cfg_name] = toml_document()
                    cls.values[cfg_name].add(
                        toml_comment(get_locale.t("config.header.line.1", locale_failed_prompt=False))
                    )
                    cls.values[cfg_name].add(
                        toml_comment(get_locale.t("config.header.line.2", locale_failed_prompt=False))
                    )
                    cls.values[cfg_name].add(
                        toml_comment(get_locale.t("config.header.line.3", locale_failed_prompt=False))
                    )
                if (
                    target not in cls.values[cfg_name]
                ):  # assume the child table name is the same as the parent table name
                    if target == "config":
                        table_comment_key = "config.table.config"  # i18n comment
                    elif target == "secret":
                        table_comment_key = "config.table.secret"
                    else:
                        is_secret = target.endswith("_secret")

                        if target.startswith("bot_"):
                            prefix = "bot"
                        elif target.startswith("module_"):
                            prefix = "module"
                        else:
                            prefix = target.split("_")[0]

                        table_comment_key = f"config.table.{'secret' if is_secret else 'config'}_{prefix}"
                    cls.values[cfg_name].add(nl())
                    cls.values[cfg_name].add(target, toml_document())
                    cls.values[cfg_name][target].add(
                        toml_comment(get_locale.t(table_comment_key, locale_failed_prompt=False))
                    )

                try:
                    cls.values[cfg_name][target].add(q, value)
                except KeyAlreadyPresent:
                    cls.values[cfg_name][target][q] = value
                finally:
                    if target.startswith("bot_") and not target.endswith("_secret") and q == "enable":
                        qc = "config.comments.bot.enable"
                    else:
                        qc = f"config.comments.{target}.{q}"
                    # get the comment for the key from locale
                    localed_comment = get_locale.t(qc, locale_failed_prompt=False)
                    if localed_comment != qc:
                        cls.values[cfg_name][target].value.item(q).comment(localed_comment)

            if _generate:
                return

            cls.save()
            cls.load()

    @classmethod
    def delete(cls, q: str, table_name: str | None = None) -> bool:
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
    def switch_config_path(cls, path: "Path"):
        cls.config_path = path.resolve()
        cls._tss = {}
        cls.config_file_list = [cfg.name for cfg in cls.config_path.glob("*.toml")]
        cls.values = {}
        cls._watch_lock = False
        cls.load()


CFGManager.load()


def Config(
    q: str,
    default: Any | None = None,
    cfg_type: type | tuple | None = None,
    secret: bool = False,
    table_name: str | None = None,
    get_url: bool = False,
    _global: bool = False,
    _generate: bool = False,
) -> Any:
    """
    获取配置文件中的配置项。

    :param q: 配置项键名。
    :param default: 默认值。
    :param cfg_type: 配置项类型。
    :param secret: 是否为密钥配置项。（默认为False）
    :param table_name: 配置项表名。
    :param get_url: 是否为URL配置项。（默认为False）
    :param _global: 内部变量，是否在所有表中查找配置项。（默认为False）
    :param _generate: 内部变量，生成配置文件时使用。（默认为False）
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
