"""配置存取接口。"""

import datetime
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Protocol, runtime_checkable

ALLOWED_TYPES = (bool, datetime.datetime, datetime.date, float, int, list, str)


@runtime_checkable
class ConfigSource(Protocol):
    """配置来源的读取与写入接口。"""

    readonly: bool

    def has(self, q: str, secret: bool = False, table_name: str | None = None) -> bool: ...

    def get(
        self,
        q: str,
        default: Any | None = None,
        cfg_type: type | tuple | None = None,
        secret: bool = False,
        table_name: str | None = None,
        _global: bool = False,
        _generate: bool = False,
        standalone_comment_keys: tuple[str, ...] = (),
    ) -> Any: ...

    def write(
        self,
        q: str,
        value: Any | None,
        cfg_type: type | tuple | None = None,
        secret: bool = False,
        table_name: str | None = None,
        _generate: bool = False,
        standalone_comment_keys: tuple[str, ...] = (),
    ) -> None: ...

    def delete(self, q: str, table_name: str | None = None) -> bool: ...

    def save(self) -> None: ...


_source: ConfigSource | None = None


def get_source() -> ConfigSource:
    """返回当前的配置来源。

    :return: 配置来源实现，尚未设置时为 ``CFGManager``。
    """
    global _source
    if _source is None:
        from core.builtins.config.manager import CFGManager

        _source = CFGManager
    return _source


def set_source(source: ConfigSource | None) -> None:
    """设置配置来源。

    :param source: 新的配置来源，传 ``None`` 表示恢复默认实现。
    """
    global _source
    _source = source


@contextmanager
def use_source(source: ConfigSource) -> Iterator[None]:
    """在上下文内替换配置来源。

    :param source: 上下文生效期间使用的配置来源。
    """
    previous = get_source()
    set_source(source)
    try:
        yield
    finally:
        set_source(previous)


__all__ = ["ALLOWED_TYPES", "ConfigSource", "get_source", "set_source", "use_source"]
