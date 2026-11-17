from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from typing import Any

from attrs import define
from satori import element as sat
from satori.parser import parse

from bots.satori.info import (
    client_name,
    sender_prefix,
    target_channel_prefix,
    target_private_prefix,
)
from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import (
    AudioElement,
    BaseElement,
    EmbedElement,
    ImageElement,
    MentionElement,
    PlainElement,
    RawElement,
    URLElement,
    VideoElement,
)
from core.builtins.message.mention import InlineMention, iter_at_code

Uploader = Callable[[ImageElement | AudioElement | VideoElement], Awaitable[str | None]]

_STYLE_ELEMENTS = (
    sat.Bold,
    sat.Italic,
    sat.Underline,
    sat.Strikethrough,
    sat.Spoiler,
    sat.Code,
    sat.Superscript,
    sat.Subscript,
)


@define
class TargetAddress:
    """场景 ID 中记录的定位信息。"""

    platform: str
    is_private: bool
    guild_id: str | None
    raw_id: str


@define
class InboundMessage:
    """由 Satori 消息内容解析出的入站结果。"""

    messages: MessageChain
    at_bot: bool
    addressed_other: bool
    reply_id: str | None


def build_channel_target_id(platform: str, guild_id: str, channel_id: str) -> str:
    """生成群聊场景 ID。"""
    return f"{target_channel_prefix}|{platform}|{guild_id}|{channel_id}"


def build_private_target_id(platform: str, user_id: str) -> str:
    """生成私聊场景 ID。"""
    return f"{target_private_prefix}|{platform}|{user_id}"


def build_sender_id(platform: str, user_id: str) -> str:
    """生成用户 ID。"""
    return f"{sender_prefix}|{platform}|{user_id}"


def parse_target_id(target_id: str | None) -> TargetAddress | None:
    """解析场景 ID；不属于本适配器时返回 None。"""
    if not target_id:
        return None
    parts = target_id.split("|")
    if len(parts) < 3 or parts[0] != client_name:
        return None
    if parts[1] == "Channel":
        if len(parts) < 5:
            return None
        return TargetAddress(platform=parts[2], is_private=False, guild_id=parts[-2], raw_id=parts[-1])
    if parts[1] == "Private":
        if len(parts) < 4:
            return None
        return TargetAddress(platform=parts[2], is_private=True, guild_id=None, raw_id=parts[-1])
    return None


def parse_sender_id(sender_id: str | None) -> tuple[str, str] | None:
    """解析用户 ID，返回平台名与底层用户 ID。"""
    if not sender_id:
        return None
    parts = sender_id.split("|")
    if len(parts) < 3 or parts[0] != client_name or parts[1] in {"Channel", "Private"}:
        return None
    return parts[1], parts[-1]


def common_id(value: str) -> str:
    """取带前缀 ID 的最后一段，即平台侧原始 ID。"""
    return value.split("|")[-1]


def _first_meaningful_element(elements: Iterable[sat.Element]) -> sat.Element | None:
    for element in elements:
        if isinstance(element, sat.Text) and not element.text.strip():
            continue
        if isinstance(element, sat.Quote) and element.id:
            continue
        return element
    return None


def _plain_text(elements: Iterable[sat.Element]) -> str:
    buffer: list[str] = []
    for element in elements:
        if isinstance(element, sat.Text):
            buffer.append(element.text)
        elif isinstance(element, sat.Br | sat.Paragraph):
            buffer.append("\n")
        else:
            buffer.append(_plain_text(element.children))
    return "".join(buffer)


def parse_inbound(content: str | None, bot_id: str | None) -> InboundMessage:
    """把 Satori 消息内容解析为消息链，并判定首位提及与引用。"""
    elements = sat.transform(parse(content or ""))
    first = _first_meaningful_element(elements)
    at_bot = isinstance(first, sat.At) and bot_id is not None and first.id == bot_id
    addressed_other = isinstance(first, sat.At) and not at_bot and first.id is not None

    values: list[BaseElement] = []
    text_buffer: list[str] = []
    reply_id: str | None = None

    def flush_text() -> None:
        if text_buffer:
            values.append(PlainElement.assign("".join(text_buffer)))
            text_buffer.clear()

    def append_element(element: sat.Element) -> None:
        nonlocal reply_id
        if isinstance(element, sat.Text):
            text_buffer.append(element.text)
            return
        if isinstance(element, sat.Quote):
            if element.id:
                reply_id = element.id
            return
        if isinstance(element, sat.At):
            if bot_id is not None and element.id == bot_id:
                return
            flush_text()
            if element.type:
                values.append(PlainElement.assign(f"@{element.type}"))
            elif element.id:
                values.append(PlainElement.assign(f"{sender_prefix}|{element.id}"))
            return
        if isinstance(element, sat.Sharp):
            flush_text()
            values.append(PlainElement.assign(f"#{element.name or element.id}"))
            return
        if isinstance(element, sat.Emoji):
            flush_text()
            values.append(PlainElement.assign(f"[{element.name or element.id}]"))
            return
        if isinstance(element, sat.Link):
            text_buffer.append(element.href)
            return
        if isinstance(element, sat.Image):
            flush_text()
            values.append(ImageElement.assign(element.src))
            return
        if isinstance(element, sat.Audio):
            flush_text()
            values.append(AudioElement.assign(element.src))
            return
        if isinstance(element, sat.Video):
            flush_text()
            values.append(VideoElement.assign(element.src))
            return
        if isinstance(element, sat.File):
            flush_text()
            values.append(PlainElement.assign(element.title or element.src))
            return
        if isinstance(element, sat.Author):
            text_buffer.append(_plain_text(element.children) or element.name or element.id)
            return
        if isinstance(element, sat.Br | sat.Paragraph):
            text_buffer.append("\n")
            return
        if isinstance(element, sat.Message):
            for child in element.children:
                append_element(child)
            return
        if isinstance(element, _STYLE_ELEMENTS):
            for child in element.children:
                append_element(child)
            return
        # 自定义元素没有统一语义，仅保留其中可读的文本，避免把标记原样透传给解析器
        for child in element.children:
            append_element(child)

    for element in elements:
        append_element(element)
    flush_text()

    return InboundMessage(
        messages=MessageChain.assign(values),
        at_bot=at_bot,
        addressed_other=addressed_other,
        reply_id=reply_id,
    )


def resolve_at_code(element: PlainElement) -> list[sat.Element]:
    """把纯文本中的 AT 码转换为 `<at>` 元素。"""
    result: list[sat.Element] = []
    parts = iter_at_code(element.text) if element.allow_parse else (element.text,)
    for part in parts:
        if isinstance(part, InlineMention):
            if part.client == client_name:
                result.append(sat.At(id=part.id))
            else:
                result.append(sat.Text(part.raw))
        elif part:
            result.append(sat.Text(part))
    return result


def _append_text(elements: list[sat.Element], text: str) -> None:
    if not text:
        return
    # Satori 会把标签边界处含换行的空白当作排版空白丢弃，行内换行改用 <br> 表达。
    for index, part in enumerate(text.replace("\r\n", "\n").replace("\r", "\n").split("\n")):
        if index:
            elements.append(sat.Br())
        if not part:
            continue
        if elements and isinstance(elements[-1], sat.Text):
            elements[-1].text += part
        else:
            elements.append(sat.Text(part))


def _embed_text(element: EmbedElement) -> str:
    lines: list[str] = []
    for value in (element.title, element.description, element.author):
        if value:
            lines.append(value)
    fields = element.fields if isinstance(element.fields, list) else [element.fields] if element.fields else []
    for field in fields:
        lines.append(f"{field.name}: {field.value}")
    if element.footer:
        lines.append(element.footer)
    if element.url:
        lines.append(element.url)
    return "\n".join(lines)


async def convert_chain_to_elements(
    session_info: Any,
    message: MessageChain,
    *,
    bot_ids: set[str],
    upload: Uploader,
    quote: bool = True,
) -> list[sat.Element]:
    """把消息链转换为 Satori 消息元素。"""
    elements: list[sat.Element] = []
    if quote and session_info.message_id:
        elements.append(sat.Quote(id=session_info.message_id))

    has_content = False

    def separate() -> None:
        nonlocal has_content
        if has_content and elements and not isinstance(elements[-1], sat.Br):
            elements.append(sat.Br())
        has_content = True

    for element in message.as_sendable(session_info):
        if isinstance(element, PlainElement):
            parts = [part for part in resolve_at_code(element) if not (isinstance(part, sat.At) and part.id in bot_ids)]
            if not parts:
                continue
            separate()
            for part in parts:
                if isinstance(part, sat.Text):
                    _append_text(elements, part.text)
                else:
                    elements.append(part)
        elif isinstance(element, MentionElement):
            separate()
            if element.client == client_name and element.id not in bot_ids:
                elements.append(sat.At(id=element.id))
            else:
                _append_text(elements, " ")
        elif isinstance(element, ImageElement):
            src = await upload(element)
            if src:
                separate()
                elements.append(sat.Image.of(url=src))
        elif isinstance(element, AudioElement):
            src = await upload(element)
            if src:
                separate()
                elements.append(sat.Audio.of(url=src))
        elif isinstance(element, VideoElement):
            src = await upload(element)
            if src:
                separate()
                elements.append(sat.Video.of(url=src))
        elif isinstance(element, URLElement):
            if element.url:
                separate()
                _append_text(elements, element.url)
        elif isinstance(element, EmbedElement):
            text = _embed_text(element)
            if text:
                separate()
                _append_text(elements, text)
        elif isinstance(element, RawElement):
            if element.value:
                separate()
                _append_text(elements, element.value)
        else:
            text = str(element)
            if text:
                separate()
                _append_text(elements, text)

    return elements
