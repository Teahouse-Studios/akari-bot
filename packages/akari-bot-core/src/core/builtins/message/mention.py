"""行内 AT 码模块 - AT 码的解析与渲染。"""

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
class InlineMention:
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
        """是否为全体提及。"""
        return not self.id.isdigit()


def iter_at_code(text: str) -> Iterator[str | InlineMention]:
    """按出现顺序切分文本，依次产出普通文本片段与 AT 码。

    :param text: 待切分的文本。
    :return: `str` 与 `InlineMention` 交替的迭代器。
    """
    position = 0
    for match in _AT_CODE_PATTERN.finditer(text):
        if match.start() > position:
            yield text[position : match.start()]
        yield InlineMention(
            client=match.group(1),
            id=match.group(2),
            raw=match.group(0),
            start=match.start(),
            end=match.end(),
        )
        position = match.end()
    if position < len(text):
        yield text[position:]


def render_at_code(text: str, client: str, render: Callable[[InlineMention], str]) -> str:
    """将本平台的 AT 码替换为平台特定的提及语法。

    :param text: 包含 AT 码的文本。
    :param client: 当前平台标识（如 `QQ`、`Discord`）。
    :param render: 渲染本平台 AT 码的回调。
    :return: 替换后的文本。
    """
    parts: list[str] = []
    for part in iter_at_code(text):
        if isinstance(part, InlineMention):
            parts.append(render(part) if part.client == client else part.raw)
        else:
            parts.append(part)
    return "".join(parts)


def spans_at_code(text: str) -> list[tuple[int, int]]:
    """列出文本中所有 AT 码的区间。

    :param text: 待检查的文本。
    :return: AT 码区间的列表，元素为 `(start, end)`。
    """
    return [(match.start(), match.end()) for match in _at_code_SPAN_PATTERN.finditer(text)]


def wrap_sender_id(text: str, sender_prefix: str) -> str:
    """将文本中的用户 ID 引用包装为 AT 码。

    :param text: 包含用户 ID 的文本。
    :param sender_prefix: 用户 ID 的前缀（如 `QQ`）。
    :return: 包装后的文本。
    """
    # 转义前缀中的特殊字符（如 `|`），避免其被当作正则元字符
    sender_prefix = re.escape(sender_prefix)
    # 负向后瞻断言确保不会重复包装已有的 AT 码；\g<0> 引用整个匹配的字符串
    return re.sub(rf"(?<!<AT:)(?<!<@:){sender_prefix}\|\w+", r"<AT:\g<0>>", text)


__all__ = [
    "InlineMention",
    "iter_at_code",
    "render_at_code",
    "spans_at_code",
    "wrap_sender_id",
]
