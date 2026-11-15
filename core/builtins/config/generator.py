"""配置项的生成与注释维护。

缺失配置项的补写、i18n 注释解析与 ``{I18N:}`` 标记修复集中在此模块，
存取层与模板层均不直接依赖 i18n。
"""

import re
from typing import Any

from tomlkit import TOMLDocument, comment as toml_comment, document as toml_document, nl
from tomlkit.exceptions import KeyAlreadyPresent
from tomlkit.items import AoT, Table

from core.builtins.config.interface import get_source
from core.constants.default import default_locale
from core.i18n import Locale

I18N_COMMENT_PATTERN = re.compile(r"^#\s*\{I18N:(?P<key>[^}]+)}\s*$")

# 已补写过缺失键的模板。同一模板在进程内只处理一次，避免重复扫描全部字段。
_ensured: set[type] = set()


def localized_config_text(locale: Locale, key: str) -> str | None:
    localized = locale.t(key, locale_failed_prompt=False)
    if localized in (key, f"{{I18N:{key}}}"):
        return None
    return localized


def write_missing_key(
    values: dict[str, TOMLDocument],
    *,
    q: str,
    value: Any,
    secret: bool,
    table_name: str | None,
    standalone_comment_keys: tuple[str, ...] = (),
) -> None:
    """将缺失的配置项写入内存中的文档，并附带文件头、表头与键注释。

    :param values: 配置文件名到文档的映射。
    :param q: 配置项键名，须已转小写。
    :param value: 写入值。
    :param secret: 是否写入密钥表。
    :param table_name: 配置项表名，须已归一化。
    :param standalone_comment_keys: 生成字段前独立注释块所使用的 i18n 键。
    """
    if table_name and table_name != "config":
        cfg_name = table_name
        target = f"{table_name}{'_secret' if secret else ''}"
    else:
        cfg_name = "config"
        target = "secret" if secret else "config"

    # 此处不可再经由来源实现获取 default_locale：配置文件一旦损坏，读取同样失败，
    # 将再次进入本分支形成递归。改为直接读取顶层键，取不到则使用默认值。
    get_locale = Locale(values.get("config", {}).get("default_locale") or default_locale)
    if cfg_name not in values:
        values[cfg_name] = toml_document()
        for header_key in ("config.header.line.1", "config.header.line.2", "config.header.line.3"):
            if header_comment := localized_config_text(get_locale, header_key):
                values[cfg_name].add(toml_comment(header_comment))
    if target not in values[cfg_name]:
        if target == "config":
            table_comment_key = "config.table.config"
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
        values[cfg_name].add(nl())
        values[cfg_name].add(target, toml_document())
        if table_comment := localized_config_text(get_locale, table_comment_key):
            values[cfg_name][target].add(toml_comment(table_comment))

    try:
        standalone_comments = [
            text for key in standalone_comment_keys if (text := localized_config_text(get_locale, key)) is not None
        ]
        if standalone_comments:
            values[cfg_name][target].add(nl())
            for standalone_comment in standalone_comments:
                values[cfg_name][target].add(toml_comment(standalone_comment))
        values[cfg_name][target].add(q, value)
    except KeyAlreadyPresent:
        values[cfg_name][target][q] = value
    finally:
        if target.startswith("bot_") and not target.endswith("_secret") and q == "enable":
            qc = "config.comments.bot.enable"
        else:
            qc = f"config.comments.{target}.{q}"
        if localed_comment := localized_config_text(get_locale, qc):
            values[cfg_name][target].value.item(q).comment(localed_comment)


def resolve_generated_value(value: Any, cfg_type: type | tuple | None) -> Any:
    """按配置项类型生成写入缺失键的占位值。

    :param value: 调用方提供的默认值。
    :param cfg_type: 配置项类型。
    :return: 待写入的值；默认值为 ``None`` 时返回形如 ``<Replace me ...>`` 的占位符。
    """
    if value is not None:
        return value
    cfg_type_str = None
    if cfg_type:
        if isinstance(cfg_type, tuple):
            cfg_type_str = "(" + ", ".join(map(lambda ty: ty.__name__, cfg_type)) + ")"
        else:
            # 联合类型等对象不具有 __name__，无法取得时退回通用占位符，避免生成注释的过程中断
            cfg_type_str = getattr(cfg_type, "__name__", None)
    # 生成模式下无论类型是否可用，均须写入占位符：
    # 若保留 None，写入不会建立该配置项，随后读取其注释时将抛出 NonExistentKey
    if cfg_type_str == "list":
        return []
    if cfg_type_str:
        return f"<Replace me with {cfg_type_str} value>"
    return "<Replace me>"


def repair_i18n_comments(values: dict[str, TOMLDocument]) -> int:
    """翻译配置中遗留的 ``{I18N:key}`` 注释标记。

    :param values: 配置文件名到文档的映射。
    :return: 被替换或清空的注释数量。
    """
    locale = Locale(values.get("config", {}).get("default_locale") or default_locale)
    # 该方法也可能被独立脚本调用。若调用方尚未连接 i18n 快照，所有键都会表现为未翻译；
    # 此时不得把已有标记误判为过时内容并批量清空。
    if localized_config_text(locale, "config.header.line.1") is None:
        return 0
    repaired = 0

    def repair_container(container):
        nonlocal repaired
        for _, item in container.body:
            try:
                comment = item.trivia.comment
            except (AttributeError, RuntimeError):
                comment = ""

            if match := I18N_COMMENT_PATTERN.fullmatch(comment):
                localized = localized_config_text(locale, match.group("key"))
                if localized is None:
                    item.trivia.comment_ws = ""
                    item.trivia.comment = ""
                else:
                    item.comment(localized)
                repaired += 1

            if isinstance(item, Table):
                repair_container(item.value)
            elif isinstance(item, AoT):
                for table in item.body:
                    repair_container(table.value)

    for document in values.values():
        repair_container(document)
    return repaired


def ensure_fields(cls: type) -> None:
    """为模板类补写配置文件中缺失的键。

    :param cls: 由配置装饰器处理过的模板类。
    """
    source = get_source()
    if source.readonly:
        return
    if cls in _ensured:
        return
    for field in cls.__config_fields__.values():
        if source.has(field["q"], field["secret"], field["table_name"]):
            continue
        default = field["default"]
        source.get(
            field["q"],
            default if default != "" else None,
            field["cfg_type"],
            field["secret"],
            field["table_name"],
            _generate=True,
            standalone_comment_keys=field["standalone_comment_keys"],
        )
        # 逐个字段写盘：写入过程会触发 watch() 热重载，整批结束再保存会丢失中途重载前的改动。
        source.save()
    _ensured.add(cls)


__all__ = [
    "I18N_COMMENT_PATTERN",
    "ensure_fields",
    "localized_config_text",
    "repair_i18n_comments",
    "resolve_generated_value",
    "write_missing_key",
]
