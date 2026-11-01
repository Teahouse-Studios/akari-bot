"""测试期配置项替身。

配置模板的属性访问每次都经 ``CFGManager.get()`` 取值，因此替换该入口即可覆盖配置项，
既不读取也不改写任何配置文件；退出上下文后原值自动恢复。
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from core.config import CFGManager

_MISSING = object()

# 还原时写回 classmethod 描述符本身，保持 CFGManager.get 在类上的原始形态
_original_descriptor = CFGManager.__dict__["get"]
_original_get = CFGManager.get
_overrides: dict[tuple[str | None, bool, str], Any] = {}
_depth = 0


def _normalize_table(table_name: str | None, secret: bool) -> tuple[str | None, bool]:
    if not table_name:
        return table_name, secret
    table_name = table_name.lower()
    # 与 CFGManager 的表名归一化保持一致：secret 与 *_secret 都指向 config 文件的密钥表
    if table_name == "secret":
        return "config", True
    if table_name.endswith("_secret"):
        return table_name.removesuffix("_secret"), True
    return table_name, secret


def _field_key(config_cls: type, name: str) -> tuple[str | None, bool, str]:
    fields = getattr(config_cls, "__config_fields__", None)
    if not isinstance(fields, dict) or name not in fields:
        raise AttributeError(f"{config_cls.__name__} has no config field {name!r}")
    field = fields[name]
    table_name, secret = _normalize_table(field.get("table_name"), bool(field.get("secret")))
    return table_name, secret, str(field.get("q", name)).lower()


def _lookup(q: str, table_name: str | None, secret: bool, global_: bool) -> Any:
    q = q.lower()
    table_name, secret = _normalize_table(table_name, secret)
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


def _mock_get(
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
    return _original_get(q, default, cfg_type, secret, table_name, _global, _generate, standalone_comment_keys)


def _install() -> None:
    global _depth
    if _depth == 0:
        CFGManager.get = _mock_get
    _depth += 1


def _uninstall() -> None:
    global _depth
    _depth -= 1
    if _depth == 0:
        setattr(CFGManager, "get", _original_descriptor)


@contextmanager
def mock_config(config_cls: type, /, **values: Any) -> Iterator[None]:
    """在上下文内临时覆盖配置项。

    覆盖只作用于进程内的配置读取，不读写配置文件；退出后恢复原取值。

    :param config_cls: 配置模板类，例如 ``CoreConfig``。
    :param values: 字段名与临时取值，形如 ``use_emote=True``。
    """
    if not values:
        raise ValueError("mock_config requires at least one config field.")
    # 先解析全部字段，避免字段名有误时已写入的覆盖残留
    keys = [(name, _field_key(config_cls, name)) for name in values]
    saved: list[tuple[tuple[str | None, bool, str], Any]] = []
    for name, key in keys:
        saved.append((key, _overrides.get(key, _MISSING)))
        _overrides[key] = values[name]
    _install()
    try:
        yield
    finally:
        for key, previous in reversed(saved):
            if previous is _MISSING:
                _overrides.pop(key, None)
            else:
                _overrides[key] = previous
        _uninstall()


__all__ = ["mock_config"]
