"""测试期配置项替身。

配置模板的属性访问经 :class:`~core.builtins.config.interface.ConfigSource` 取值，因此替换来源
即可覆盖配置项，既不读取也不改写任何配置文件；退出上下文后原值自动恢复。
"""

from contextlib import AbstractContextManager
from typing import Any

from core.builtins.config.interface import ConfigSource, get_source, use_source
from core.builtins.config.manager import normalize_table

_MISSING = object()

_overrides: dict[tuple[str | None, bool, str], Any] = {}
# 替换由最外层上下文持有，嵌套进入时不再重复替换，也就不会被内层退出提前还原
_source_context: Any = None
_depth = 0


def _field_key(config_cls: type, name: str) -> tuple[str | None, bool, str]:
    fields = getattr(config_cls, "__config_fields__", None)
    if not isinstance(fields, dict) or name not in fields:
        raise AttributeError(f"{config_cls.__name__} has no config field {name!r}")
    field = fields[name]
    table_name, secret = normalize_table(field.get("table_name"), bool(field.get("secret")))
    return table_name, secret, str(field.get("q", name)).lower()


def _lookup(q: str, table_name: str | None, secret: bool, global_: bool) -> Any:
    q = q.lower()
    table_name, secret = normalize_table(table_name, secret)
    value = _overrides.get((table_name, secret, q), _MISSING)
    if value is not _MISSING:
        return value
    if table_name is None:
        # 未限定表名的读取要么只在 config.toml 内查找，要么按 _global 遍历全部表
        candidates = [
            value
            for (candidate_table, candidate_secret, candidate_q), value in _overrides.items()
            if candidate_q == q and candidate_secret == secret and (global_ or candidate_table in (None, "config"))
        ]
        if len(candidates) == 1:
            return candidates[0]
    return _MISSING


class _MockSource:
    """在底层来源之上叠加一层取值覆盖。"""

    def __init__(self, base: ConfigSource):
        self._base = base

    @property
    def readonly(self) -> bool:
        return self._base.readonly

    def has(self, q: str, secret: bool = False, table_name: str | None = None) -> bool:
        return self._base.has(q, secret, table_name)

    def get(
        self,
        q: str,
        default: Any = None,
        cfg_type: type | tuple | None = None,
        secret: bool = False,
        table_name: str | None = None,
        _global: bool = False,
        _generate: bool = False,
        standalone_comment_keys: tuple[str, ...] = (),
    ) -> Any:
        # 生成模式写入的是模板默认值，不能被测试覆盖值污染
        if not _generate:
            value = _lookup(q, table_name, secret, _global)
            if value is not _MISSING:
                return value
        return self._base.get(q, default, cfg_type, secret, table_name, _global, _generate, standalone_comment_keys)

    def write(
        self,
        q: str,
        value: Any | None,
        cfg_type: type | tuple | None = None,
        secret: bool = False,
        table_name: str | None = None,
        _generate: bool = False,
        standalone_comment_keys: tuple[str, ...] = (),
    ) -> None:
        self._base.write(q, value, cfg_type, secret, table_name, _generate, standalone_comment_keys)

    def delete(self, q: str, table_name: str | None = None) -> bool:
        return self._base.delete(q, table_name)

    def save(self) -> None:
        self._base.save()


def _install() -> None:
    global _depth, _source_context
    if _depth == 0:
        _source_context = use_source(_MockSource(get_source()))
        _source_context.__enter__()
    _depth += 1


def _uninstall() -> None:
    global _depth, _source_context
    _depth -= 1
    if _depth == 0:
        source_context, _source_context = _source_context, None
        source_context.__exit__(None, None, None)


class mock_config(AbstractContextManager[None]):
    """在上下文内临时覆盖配置项。

    覆盖只作用于进程内的配置读取，不读写配置文件；退出后恢复原取值。

    :param config_cls: 配置模板类，例如 ``CoreConfig``。
    :param values: 字段名与临时取值，形如 ``use_emote=True``。
    """

    def __init__(self, config_cls: type, /, **values: Any):
        if not values:
            raise ValueError("mock_config requires at least one config field.")
        # 先解析全部字段，避免字段名有误时已写入的覆盖残留
        self._entries = [(_field_key(config_cls, name), value) for name, value in values.items()]
        self._saved: list[list[tuple[tuple[str | None, bool, str], Any]]] = []

    def __enter__(self) -> None:
        saved = [(key, _overrides.get(key, _MISSING)) for key, _ in self._entries]
        self._saved.append(saved)
        for key, value in self._entries:
            _overrides[key] = value
        _install()

    def __exit__(self, *exc_info: object) -> None:
        for key, previous in reversed(self._saved.pop()):
            if previous is _MISSING:
                _overrides.pop(key, None)
            else:
                _overrides[key] = previous
        _uninstall()


__all__ = ["mock_config"]
