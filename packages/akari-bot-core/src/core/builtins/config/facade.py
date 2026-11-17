"""配置读取门面。"""

from typing import Any

from core.builtins.config.interface import get_source
from core.utils.func import format_url


def Config(
    q: str,
    default: Any | None = None,
    cfg_type: type | tuple | None = None,
    secret: bool = False,
    table_name: str | None = None,
    get_url: bool = False,
    _global: bool = False,
    _generate: bool = False,
    standalone_comment_keys: tuple[str, ...] = (),
) -> Any:
    """
    获取配置文件中的配置项。仅用于键名在运行时动态确定的场景。

    :param q: 配置项键名。
    :param default: 默认值。
    :param cfg_type: 配置项类型。
    :param secret: 是否为密钥配置项。（默认为False）
    :param table_name: 配置项表名。
    :param get_url: 是否为URL配置项。（默认为False）
    :param _global: 内部变量，是否在所有表中查找配置项。（默认为False）
    :param _generate: 内部变量，生成配置文件时使用。（默认为False）
    :param standalone_comment_keys: 生成字段前独立注释块所使用的 i18n 键
    :return: 配置文件中对应配置项的值。
    """
    value = get_source().get(
        q,
        default,
        str if get_url else cfg_type,
        secret,
        table_name,
        _global,
        _generate,
        standalone_comment_keys,
    )
    return format_url(value) if get_url else value


__all__ = ["Config"]
