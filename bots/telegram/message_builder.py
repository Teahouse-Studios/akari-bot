"""Telegram 消息聚合负载构建。"""

import asyncio
import re
from html import escape
from html.parser import HTMLParser

from aiogram.types import FSInputFile, InputMediaAudio, InputMediaPhoto
from attrs import define, field

from bots.telegram.info import client_name
from core.builtins.filter import filter_badwords
from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import (
    ActionTextElement,
    ButtonFrameElement,
    ButtonRows,
    ImageElement,
    MentionElement,
    PlainElement,
    VoiceElement,
)
from core.builtins.session.info import SessionInfo
from core.logger import Logger
from core.utils.image_split import image_split


@define(frozen=True)
class _HTMLContext:
    tag: str
    raw: str


@define(frozen=True)
class _HTMLAtom:
    raw: str
    contexts: tuple[_HTMLContext, ...] = field(factory=tuple)
    newline: bool = False


@define
class TelegramContent:
    """聚合后的 Telegram 文本与媒体。"""

    text: str = ""
    images: list = field(factory=list)
    audio: list = field(factory=list)
    action_texts: list[ActionTextElement] = field(factory=list)
    button_rows: list[ButtonRows] = field(factory=list)


@define
class TelegramTextOperation:
    text: str
    reply_markup: object | None = None


@define
class TelegramPhotoOperation:
    photo: object
    caption: str | None = None
    reply_markup: object | None = None


@define
class TelegramAudioOperation:
    audio: object
    caption: str | None = None
    reply_markup: object | None = None


@define
class TelegramMediaGroupOperation:
    media: list
    attach_markup_after_send: bool = False


class _HTMLAtomParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.contexts: list[_HTMLContext] = []
        self.atoms: list[_HTMLAtom] = []

    def handle_starttag(self, tag: str, attrs):
        self.contexts.append(_HTMLContext(tag, self.get_starttag_text()))

    def handle_endtag(self, tag: str):
        for index in range(len(self.contexts) - 1, -1, -1):
            if self.contexts[index].tag == tag:
                del self.contexts[index:]
                break

    def handle_data(self, data: str):
        contexts = tuple(self.contexts)
        self.atoms.extend(_HTMLAtom(char, contexts, char == "\n") for char in data)

    def handle_entityref(self, name: str):
        self.atoms.append(_HTMLAtom(f"&{name};", tuple(self.contexts)))

    def handle_charref(self, name: str):
        self.atoms.append(_HTMLAtom(f"&#{name};", tuple(self.contexts)))

    def handle_startendtag(self, tag: str, attrs):
        raw = self.get_starttag_text()
        self.atoms.append(_HTMLAtom(raw, tuple(self.contexts)))


AT_CODE_PATTERN = re.compile(r"<(?:AT|@):([^\|]+)\|(?:.*?\|)?([^\|>]+)>")


def _escape_telegram_text(text: str, parse_mentions: bool = True) -> str:
    """转义普通文本，仅将本平台 AT 码转换为受控的 Telegram HTML。"""
    if not parse_mentions:
        return escape(text)

    result = []
    start = 0
    for match in AT_CODE_PATTERN.finditer(text):
        result.append(escape(text[start : match.start()]))
        if match.group(1) == client_name:
            user_id = escape(match.group(2), quote=True)
            result.append(f'<a href="tg://user?id={user_id}">@{user_id}</a>')
        else:
            result.append(escape(match.group(0)))
        start = match.end()
    result.append(escape(text[start:]))
    return "".join(result)


def _render_html_atoms(atoms: list[_HTMLAtom]) -> str:
    result = []
    current: tuple[_HTMLContext, ...] = ()
    for atom in atoms:
        common = 0
        while common < min(len(current), len(atom.contexts)) and current[common] == atom.contexts[common]:
            common += 1
        result.extend(f"</{context.tag}>" for context in reversed(current[common:]))
        result.extend(context.raw for context in atom.contexts[common:])
        result.append(atom.raw)
        current = atom.contexts
    result.extend(f"</{context.tag}>" for context in reversed(current))
    return "".join(result)


def split_telegram_html(text: str, limit: int) -> list[str]:
    """按可见字符数拆分 Telegram HTML，并保持每段标签完整。"""
    if not text:
        return []
    if "<" not in text and "&" not in text:
        return _split_plain_telegram_text(text, limit)
    parser = _HTMLAtomParser()
    parser.feed(text)
    atoms = parser.atoms
    chunks = []
    start = 0
    while start < len(atoms):
        end = min(start + limit, len(atoms))
        if end < len(atoms):
            newline = next((index for index in range(end - 1, start - 1, -1) if atoms[index].newline), None)
            if newline is not None and newline > start:
                end = newline
        chunk_atoms = atoms[start:end]
        if chunk_atoms:
            chunks.append(_render_html_atoms(chunk_atoms))
        start = end + 1 if end < len(atoms) and atoms[end].newline else end
    return chunks


def _split_plain_telegram_text(text: str, limit: int) -> list[str]:
    """纯文本快速拆分，避免为每个字符创建 HTML atom 对象。"""
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + limit, len(text))
        if end < len(text):
            newline = text.rfind("\n", start, end)
            if newline > start:
                end = newline
        chunks.append(text[start:end])
        start = end + 1 if end < len(text) and text[end] == "\n" else end
    return chunks


async def collect_telegram_content(
    session_info: SessionInfo,
    message: MessageChain,
) -> TelegramContent:
    """收集完整消息链中的 Telegram 文本、图片与音频。"""
    text_parts = []
    images = []
    audio = []
    action_texts = []
    button_rows = []
    inline_pending = False
    for element in message.as_sendable(session_info):
        if isinstance(element, PlainElement):
            element.text = session_info.locale.t_str(filter_badwords(element.text))
            text = _escape_telegram_text(element.text, parse_mentions=element.allow_parse)
            if inline_pending and text_parts:
                text_parts[-1] += text
            else:
                text_parts.append(text)
            inline_pending = False
        elif isinstance(element, ActionTextElement):
            fallback = escape(element.to_plain(session_info).text)
            if text_parts:
                text_parts[-1] += fallback
            else:
                text_parts.append(fallback)
            action_texts.append(element)
            inline_pending = True
        elif isinstance(element, ButtonFrameElement):
            button_rows.extend(element.rows)
            inline_pending = False
        elif isinstance(element, MentionElement):
            if element.client == client_name and session_info.target_from in [
                f"{client_name}|Group",
                f"{client_name}|Supergroup",
            ]:
                user_id = escape(element.id, quote=True)
                text_parts.append(f'<a href="tg://user?id={user_id}">@{user_id}</a>')
            inline_pending = False
        elif isinstance(element, ImageElement):
            image_elements = await image_split(element) if element.allow_split else [element]
            for image in image_elements:
                images.append(FSInputFile(await image.get()))
            inline_pending = False
        elif isinstance(element, VoiceElement):
            audio.append(FSInputFile(element.path))
            inline_pending = False
    text = "\n".join(text_parts)
    if not text and button_rows and not images and not audio:
        text = "\u200b"
    return TelegramContent(
        text=text,
        images=images,
        audio=audio,
        action_texts=action_texts,
        button_rows=button_rows,
    )


def _group_media(items: list, media_type, caption: str | None = None) -> list:
    operations = []
    for start in range(0, len(items), 10):
        group = items[start : start + 10]
        group_caption = caption if start == 0 else None
        if len(group) == 1:
            operation_type = TelegramPhotoOperation if media_type is InputMediaPhoto else TelegramAudioOperation
            key = "photo" if media_type is InputMediaPhoto else "audio"
            operations.append(operation_type(**{key: group[0]}, caption=group_caption))
        else:
            media = [
                media_type(media=item, caption=group_caption if index == 0 else None, parse_mode="HTML")
                for index, item in enumerate(group)
            ]
            operations.append(TelegramMediaGroupOperation(media=media))
    return operations


def _split_telegram_html_head(text: str, limit: int) -> tuple[str | None, str]:
    if "<" not in text and "&" not in text:
        return text[:limit] or None, text[limit:]
    parser = _HTMLAtomParser()
    parser.feed(text)
    atoms = parser.atoms
    if not atoms:
        return None, ""
    head_atoms = atoms[:limit]
    remainder_atoms = atoms[limit:]
    return _render_html_atoms(head_atoms), _render_html_atoms(remainder_atoms) if remainder_atoms else ""


def build_telegram_operations(content: TelegramContent, reply_markup=None) -> list:
    """按平台限制把聚合内容转换成 Telegram 发送操作。"""
    has_media = bool(content.images or content.audio)
    if has_media and content.text:
        caption, remainder = _split_telegram_html_head(content.text, 1024)
        remaining_text = split_telegram_html(remainder, 4096)
    else:
        caption = None
        remaining_text = split_telegram_html(content.text, 4096)

    operations = []
    operations.extend(_group_media(content.images, InputMediaPhoto, caption=caption))
    operations.extend(_group_media(content.audio, InputMediaAudio, caption=caption if not content.images else None))
    for text_chunk in remaining_text:
        operations.append(TelegramTextOperation(text=text_chunk))

    if operations and reply_markup is not None:
        last = operations[-1]
        if isinstance(last, TelegramMediaGroupOperation):
            last.attach_markup_after_send = True
        else:
            last.reply_markup = reply_markup
    return operations


async def execute_telegram_operations(
    bot,
    chat_id,
    operations: list,
    reply_to_message_id: int | None,
    reply_markup,
) -> list:
    """执行 Telegram 发送操作并返回全部平台消息。"""
    sent_messages = []
    for index, operation in enumerate(operations):
        reply_id = reply_to_message_id if index == 0 else None
        try:
            if isinstance(operation, TelegramTextOperation):
                sent = await bot.send_message(
                    chat_id,
                    operation.text,
                    parse_mode="HTML",
                    reply_to_message_id=reply_id,
                    reply_markup=operation.reply_markup,
                )
                sent_messages.append(sent)
            elif isinstance(operation, TelegramPhotoOperation):
                sent = await bot.send_photo(
                    chat_id,
                    operation.photo,
                    caption=operation.caption,
                    parse_mode="HTML",
                    reply_to_message_id=reply_id,
                    reply_markup=operation.reply_markup,
                )
                sent_messages.append(sent)
            elif isinstance(operation, TelegramAudioOperation):
                sent = await bot.send_audio(
                    chat_id,
                    operation.audio,
                    caption=operation.caption,
                    parse_mode="HTML",
                    reply_to_message_id=reply_id,
                    reply_markup=operation.reply_markup,
                )
                sent_messages.append(sent)
            elif isinstance(operation, TelegramMediaGroupOperation):
                group = await bot.send_media_group(
                    chat_id,
                    operation.media,
                    reply_to_message_id=reply_id,
                )
                sent_messages.extend(group)
                if operation.attach_markup_after_send and group and reply_markup is not None:
                    await group[-1].edit_reply_markup(reply_markup=reply_markup)
        except asyncio.CancelledError:
            raise
        except Exception:
            Logger.exception(f"Failed to execute Telegram operation {index + 1}/{len(operations)}: ")
            break
    return sent_messages
