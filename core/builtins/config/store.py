"""TOML 配置文件的存储层。"""

import os
import time
from contextlib import contextmanager
from collections.abc import Iterator
from pathlib import Path
from time import sleep

from loguru import logger
from tomlkit import TOMLDocument, dumps as toml_dumps, parse as toml_parser

from core.constants.exceptions import ConfigOperationError, ConfigValueError


class TomlStore:
    """一个配置目录下全部 TOML 文件的内存副本。"""

    # 两次检查配置文件改动之间的最小间隔（秒）
    WATCH_INTERVAL = 1.0
    # 等待进入临界区的上限（秒）
    LOCK_TIMEOUT = 10.0
    # 锁文件被判定为陈旧的时长（秒）。该值须显著大于一次正常读写的耗时，
    # 否则会回收仍处于临界区内的进程所持有的锁，导致两个进程同时改写而使配置项互相覆盖
    LOCK_STALE = 60.0

    def __init__(self, path: Path):
        self.path = path
        self.values: dict[str, TOMLDocument] = {}
        self._mtimes: dict[str, float] = {}
        self._watch_lock = False
        self._last_watch = 0.0
        self._lock_depth = 0

    @contextmanager
    def exclusive(self) -> Iterator[None]:
        if self._lock_depth:
            self._lock_depth += 1
            try:
                yield
            finally:
                self._lock_depth -= 1
            return

        lock_path = self.path / ".config.lock"
        deadline = time.monotonic() + self.LOCK_TIMEOUT
        fd = None
        while fd is None:
            try:
                fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                # 持锁进程若被强制结束会遗留锁文件，超过时限即判定为陈旧锁并予以回收。
                try:
                    if time.time() - lock_path.stat().st_mtime > self.LOCK_STALE:
                        lock_path.unlink(missing_ok=True)
                        continue
                except OSError:
                    pass
                if time.monotonic() > deadline:
                    raise ConfigOperationError("Operation timeout.")
                sleep(0.05)
        self._lock_depth = 1
        try:
            yield
        finally:
            self._lock_depth = 0
            os.close(fd)
            lock_path.unlink(missing_ok=True)

    def load(self) -> None:
        with self.exclusive():
            try:
                for file_name in [cfg.name for cfg in self.path.glob("*.toml")]:
                    cfg_name = file_name
                    if cfg_name.endswith(".toml"):
                        cfg_name = cfg_name.removesuffix(".toml")
                    with open(self.path / file_name, "r", encoding="utf-8") as c:
                        parsed = toml_parser(c.read())
                    # 空 TOML 属于合法输入，解析不会报错。若磁盘上的文件已被清空而内存中仍有内容，
                    # 直接覆盖会在下一次保存时将该空状态写回磁盘，配置即永久丢失。
                    if not parsed and self.values.get(cfg_name):
                        logger.error(f"[Config] Config file {file_name} is empty, keeping the loaded values.")
                        continue
                    self.values[cfg_name] = parsed
                    self._mtimes[cfg_name] = (self.path / file_name).stat().st_mtime
            except Exception as e:
                raise ConfigValueError(e)

    def save(self) -> None:
        with self.exclusive():
            try:
                for cfg in self.values:
                    cfg_name = cfg
                    if not cfg_name.endswith(".toml"):
                        cfg_name += ".toml"
                    file_path = self.path / cfg_name
                    content = toml_dumps(self.values[cfg], sort_keys=True)
                    # 仅写入内容确有变化的文件。一次改写通常只涉及一个配置项，
                    # 若重写全部二十余个文件，既会延长临界区，也会触发其它进程的无谓重新加载。
                    if file_path.exists() and file_path.read_text(encoding="utf-8") == content:
                        continue
                    self._atomic_write(file_path, content)
            except Exception as e:
                raise ConfigValueError(e)

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        tmp_path = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, path)
        finally:
            tmp_path.unlink(missing_ok=True)

    def watch(self) -> None:
        if self._watch_lock:
            return
        # 若每次读取配置都对全部文件执行 stat，单次属性访问将产生数十次系统调用，
        # 代价与「读一个已在内存里的值」完全不成比例。配置改动晚至多 WATCH_INTERVAL 秒生效即可。
        now = time.monotonic()
        if now - self._last_watch < self.WATCH_INTERVAL:
            return
        self._last_watch = now

        self._watch_lock = True
        try:
            # 用一次目录扫描代替逐文件 exists() + stat()：DirEntry 自带的元数据来自目录项本身，
            # 不必为每个文件再走一次文件系统查询。
            try:
                mtimes = {
                    entry.name: entry.stat().st_mtime
                    for entry in os.scandir(self.path)
                    if entry.is_file() and entry.name.endswith(".toml")
                }
            except OSError:
                return

            for cfg in self.values:
                cfg_file = cfg if cfg.endswith(".toml") else f"{cfg}.toml"
                if cfg_file in mtimes and mtimes[cfg_file] != self._mtimes.get(cfg):
                    logger.warning("[Config] Config file has been modified, reloading...")
                    self.load()
                    break
        finally:
            # 若不置于 finally 中，一旦加载抛出异常，此后 watch() 将永久空转，磁盘上的改动无法再被读取。
            self._watch_lock = False

    def switch_path(self, path: Path) -> None:
        self.path = path.resolve()
        self.values = {}
        self._mtimes = {}
        self._watch_lock = False
        # 切换目录后必须立刻重新检查，不能让上一份目录的节流状态把首次检查挡掉
        self._last_watch = 0.0
        self.load()


__all__ = ["TomlStore"]
