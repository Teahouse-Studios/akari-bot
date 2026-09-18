"""
行内 AT 码模块 - AT 码的解析与渲染。

AT 码（`<AT:client|userid>` / `<@:client|userid>`）是嵌在**文本流内部**的提及标记，
它与链上的 `MentionElement` 语义不同：`MentionElement` 是链上的独立元素，
而 AT 码渲染后必须与前后文本同属一条文本。同理，无法渲染的 AT 码应当原样保留（而不是退化为空格占位）。

本模块是 AT 码格式知识的唯一来源：产生（`wrap_sender_id`）、切分（`iter_at_code`）、
渲染（`render_at_code`）与受保护区间（`spans_at_code`）均由这里导出。
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator

from attrs import define

# AT 码格式：<AT:client|userid> / <@:client|userid>，client 与 userid 之间允许存在额外字段。
# 注意：中间字段使用惰性 `.*?`，因此同一行内的多个 AT 码会被合并为一次匹配（取最后一个 ID）；
# 这是重构前各适配器共用的既有语义，保持原样以免改变线上输出。
_AT_CODE_PATTERN = re.compile(r"<(?:AT|@):([^\|]+)\|(?:.*?\|)?([^\|>]+)>")

# 受保护区间专用：不允许跨标签吞掉中间文本，保证相邻 AT 码之间的正文不被豁免。
_at_code_SPAN_PATTERN = re.compile(r"<(?:AT|@):[^\|>]+\|(?:[^\|>]*\|)?[^\|>]+>")


@define(frozen=True)
class InlineAt:
    """
    文本流中的一处 AT 码。

    :param client: AT 码声明的平台标识。
    :param id: 被提及的用户 ID。
    :param raw: AT 码原文，如 `<AT:QQ|123>`。
    :param start: 在所属文本中的起始下标。
    :param end: 在所属文本中的结束下标（不含）。
    """

    client: str
    id: str
    raw: str
    start: int
    end: int

    @property
    def is_broadcast(self) -> bool:
        """
        是否为全体提及。

        非数字的 `id`（如 `all`）视为全体提及，由各平台自行决定如何渲染。
        """
        return not self.id.isdigit()


def iter_at_code(text: str) -> Iterator[str | InlineAt]:
    """
    按出现顺序切分文本，依次产出普通文本片段与 AT 码。

    产出的片段可直接拼接还原原文；文本中相邻的 AT 码之间不会产生空字符串。

    :param text: 待切分的文本。
    :return: `str` 与 `InlineAt` 交替的迭代器。
    """
    position = 0
    for match in _AT_CODE_PATTERN.finditer(text):
        if match.start() > position:
            yield text[position : match.start()]
        yield InlineAt(
            client=match.group(1),
            id=match.group(2),
            raw=match.group(0),
            start=match.start(),
            end=match.end(),
        )
        position = match.end()
    if position < len(text):
        yield text[position:]


def render_at_code(text: str, client: str, render: Callable[[InlineAt], str]) -> str:
    """
    将本平台的 AT 码替换为平台特定的提及语法。

    非本平台的 AT 码原样保留；调用方负责决定是否只在允许解析时调用本函数。

    :param text: 包含 AT 码的文本。
    :param client: 当前平台标识（如 `QQ`、`Discord`）。
    :param render: 渲染本平台 AT 码的回调。
    :return: 替换后的文本。

    示例：
    ```python
        > text = "Hello <AT:QQ|123456>"
        > render_at_code(text, "QQ", lambda at: f"@{at.id}")
        'Hello @123456'
        > render_at_code(text, "Discord", lambda at: f"@{at.id}")
        'Hello <AT:QQ|123456>'  # 不匹配，保留原样
    ```
    """
    parts: list[str] = []
    for part in iter_at_code(text):
        if isinstance(part, InlineAt):
            parts.append(render(part) if part.client == client else part.raw)
        else:
            parts.append(part)
    return "".join(parts)


def spans_at_code(text: str) -> list[tuple[int, int]]:
    """
    列出文本中所有 AT 码的区间。

    供过滤器等需要豁免 AT 码结构（而非渲染它）的场景使用。
    与 :func:`iter_at_code` 不同，这里的匹配不跨标签：相邻 AT 码之间的正文不会被一并豁免。

    :param text: 待检查的文本。
    :return: AT 码区间的列表，元素为 `(start, end)`。
    """
    return [(match.start(), match.end()) for match in _at_code_SPAN_PATTERN.finditer(text)]


def wrap_sender_id(text: str, sender_prefix: str) -> str:
    """
    将文本中的用户 ID 引用包装为 AT 码。

    已包装为 AT 码的引用不会重复包装。文本中的反斜杠是普通字符，原样保留。

    :param text: 包含用户 ID 的文本。
    :param sender_prefix: 用户 ID 的前缀（如 `QQ`）。
    :return: 包装后的文本。

    示例：
    ```python
        > text = "User QQ|123456 said hello"
        > wrap_sender_id(text, "QQ")
        'User <AT:QQ|123456> said hello'
    ```
    """
    # 转义前缀中的特殊字符（如 `|`），避免其被当作正则元字符
    sender_prefix = re.escape(sender_prefix)
    # 负向后瞻断言确保不会重复包装已有的 AT 码；\g<0> 引用整个匹配的字符串
    return re.sub(rf"(?<!<AT:)(?<!<@:){sender_prefix}\|\w+", r"<AT:\g<0>>", text)


__all__ = [
    "InlineAt",
    "iter_at_code",
    "render_at_code",
    "spans_at_code",
    "wrap_sender_id",
]
