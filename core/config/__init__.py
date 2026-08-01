import datetime
import multiprocessing
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

# 环境变量名。守护进程在 spawn 子进程之前置位，spawn 会继承环境。
# 该闸门须赶在 core.config 被导入之前生效：core/config/update.py 的版本迁移是导入期执行的，
# 而 go() 中的 Info.subprocess = True 置位过迟：其前一行的 core.logger 已导入 core.config。
CONFIG_READONLY_ENV = "AKARI_CONFIG_READONLY"
CONFIG_READONLY = bool(os.environ.get(CONFIG_READONLY_ENV))

# 配置版本迁移只应发生在 pre_init 中。core.config.update 全仓仅此一处导入且为纯副作用导入，
# 跳过该导入即可，无需改动其内部的顶层代码。
if not CONFIG_READONLY:
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
    # 两次检查配置文件改动之间的最小间隔（秒）
    WATCH_INTERVAL = 1.0
    _last_watch = 0.0
    _lock_depth = 0

    # 本进程是否只读。运行期一律读这个类属性而非模块级常量，测试可直接改写。
    readonly: bool = CONFIG_READONLY
    # 授权写入的嵌套深度。用计数而非布尔：write() 内部会调用 save()，两层都须放行。
    _allow_write_depth = 0

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
    @contextmanager
    def _writable(cls):
        """临时解除只读限制，仅供 edit_* 使用。可重入。"""
        cls._allow_write_depth += 1
        try:
            yield
        finally:
            cls._allow_write_depth -= 1

    @classmethod
    def _ensure_writable(cls, q: str | None = None, table_name: str | None = None, secret: bool = False):
        """在只读进程中拒绝写入。

        配置的生成统一由 bot.py 的 pre_init() 完成，bot 与 server 子进程一律只读，
        以免同一批配置项被多个进程重复补写。交互式编辑须经 edit_write() / edit_delete()。

        :param q: 配置项键名，仅用于组装错误信息。
        :param table_name: 配置项表名，仅用于组装错误信息。
        :param secret: 是否为密钥配置项，仅用于组装错误信息。
        :raises ConfigOperationError: 当前进程只读，且不处于授权写入的作用域内。
        """
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
        cls._ensure_writable()
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
        # 每次配置读取都去 stat 一遍全部配置文件的话，一次属性访问就要几十次系统调用，
        # 代价与「读一个已在内存里的值」完全不成比例。配置改动晚至多 WATCH_INTERVAL 秒生效即可。
        now = time.monotonic()
        if now - cls._last_watch < cls.WATCH_INTERVAL:
            return
        cls._last_watch = now

        cls._watch_lock = True
        try:
            # 用一次目录扫描代替逐文件 exists() + stat()：DirEntry 自带的元数据来自目录项本身，
            # 不必为每个文件再走一次文件系统查询。
            try:
                mtimes = {
                    entry.name: entry.stat().st_mtime
                    for entry in os.scandir(cls.config_path)
                    if entry.is_file() and entry.name.endswith(".toml")
                }
            except OSError:
                return

            for cfg in cls.values:
                cfg_file = cfg if cfg.endswith(".toml") else f"{cfg}.toml"
                if cfg_file in mtimes and mtimes[cfg_file] != cls._tss.get(cfg):
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
                        # [config]
                        # foo = bar  <- get the value inside the table
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
                        # foo = bar <- if the item is not a table, assume it is a key-value pair outside the table
                        # [config]
                        # foo = bar
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
            # 与 has() 和 write() 保持一致的表名归一化。缺少这一步时，table_name="secret"
            # 会被当作一个名为 secret.toml 的独立配置文件去查找，取不到值而一律回退至默认值。
            if table_name == "secret":
                table_name, secret = "config", True
            if table_name.endswith("_secret"):
                table_name, secret = table_name.removesuffix("_secret"), True

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

        # 守卫置于此处而非方法体最前：无默认值的读取以 value=None 进入上方分支并提前返回，
        # 不涉及写入，不应抛出异常。
        cls._ensure_writable(q, table_name, secret)

        # 「重新加载 → 修改 → 保存」须在同一个临界区内完整完成。
        # 否则本进程会以过时的内存副本整体覆盖磁盘，致使其它进程期间写入的配置项丢失。
        with cls._exclusive():
            if not _generate:
                cls.load()

            found = False
            if not table_name:  # if table_name is not provided, search for the value in config.toml tables
                for t in cls.values["config"].keys():
                    if isinstance(cls.values["config"][t], Table):
                        # [config]
                        # foo = bar  <- get the value inside the table

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
                        # foo = bar <- if the item is not a table, assume it"s a key-value pair outside the table
                        # [config]
                        # foo = bar
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
        cls._ensure_writable(q, table_name)
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
    def edit_write(
        cls,
        q: str,
        value: Any | None,
        cfg_type: type | tuple | None = None,
        secret: bool = False,
        table_name: str | None = None,
    ):
        """授权写入，供交互式编辑命令与启动期的密钥自举使用。

        这是只读进程中唯一合法的写入途径。命名为 edit_* 而非给 write() 加参数，
        是为了使全部合法写入点均可经检索穷举。

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

    @classmethod
    def switch_config_path(cls, path: "Path"):
        cls.config_path = path.resolve()
        cls._tss = {}
        cls.config_file_list = [cfg.name for cfg in cls.config_path.glob("*.toml")]
        cls.values = {}
        cls._watch_lock = False
        # 切换目录后必须立刻重新检查，不能让上一份目录的节流状态把首次检查挡掉
        cls._last_watch = 0.0
        cls.load()


CFGManager.load()


def format_url(v: Any | None) -> Any | None:
    """
    将配置项中的地址补全为可直接请求的 URL。

    缺少协议头时补上 ``http://``，并确保以斜杠结尾。空值原样返回。

    :param v: 配置项的原始值。
    :return: 补全后的 URL。
    """
    if not v:
        return v
    if not re.match(r"^[a-zA-Z][a-zA-Z\d+\-.]*://", v):
        v = "http://" + v
    if v[-1] != "/":
        v += "/"
    return v


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
        v = format_url(CFGManager.get(q, default, str, secret, table_name, _global, _generate))
    else:
        v = CFGManager.get(q, default, cfg_type, secret, table_name, _global, _generate)
    return v


add_export(Config)
add_export(CFGManager)
