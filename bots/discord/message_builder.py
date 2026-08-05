"""Discord 消息聚合负载构建。"""

import discord
from attrs import define, field

from bots.discord.info import client_name, target_channel_prefix
from bots.discord.utils import convert_embed
from core.builtins.message.chain import MessageChain, match_atcode
from core.builtins.message.elements import (
    ActionTextElement,
    EmbedElement,
    ImageElement,
    MentionElement,
    PlainElement,
    VoiceElement,
)
from core.builtins.session.info import SessionInfo


@define
class DiscordPayload:
    """一次 Discord 发送调用所需的负载。"""

    content: str | None = None
    files: list[discord.File] = field(factory=list)
    embeds: list[discord.Embed] = field(factory=list)
    action_texts: list[ActionTextElement] = field(factory=list)


def split_discord_text(text: str, limit: int = 2000) -> list[str]:
    """按 Discord 限制拆分文本，优先在换行处分段。"""
    chunks = []
    remaining = text
    while remaining:
        if len(remaining) <= limit:
            chunks.append(remaining)
            break
        split_at = remaining.rfind("\n", 0, limit + 1)
        if split_at <= 0:
            split_at = limit
        chunks.append(remaining[:split_at])
        remaining = remaining[split_at + 1 :] if remaining[split_at : split_at + 1] == "\n" else remaining[split_at:]
    return chunks


async def build_discord_payloads(
    session_info: SessionInfo, message: MessageChain, enable_parse_message: bool = True
) -> list[DiscordPayload]:
    """将完整消息链聚合为受平台限制约束的 Discord 负载。"""
    text_parts = []
    files = []
    embed_units = []
    action_texts = []
    embed_index = 0
    inline_pending = False

    for element in message.as_sendable(session_info, parse_message=enable_parse_message):
        if isinstance(element, PlainElement):
            text = match_atcode(element.text, client_name, "<@{uid}>") if enable_parse_message else element.text
            if inline_pending and text_parts:
                text_parts[-1] += text
            else:
                text_parts.append(text)
            inline_pending = False
        elif isinstance(element, ActionTextElement):
            fallback = element.to_plain(session_info).text
            if text_parts:
                text_parts[-1] += fallback
            else:
                text_parts.append(fallback)
            action_texts.append(element)
            inline_pending = True
        elif isinstance(element, MentionElement):
            if element.client == client_name and session_info.target_from == target_channel_prefix:
                text_parts.append(f"<@{element.id}>")
            inline_pending = False
        elif isinstance(element, ImageElement):
            files.append(discord.File(await element.get()))
            inline_pending = False
        elif isinstance(element, VoiceElement):
            files.append(discord.File(element.path))
            inline_pending = False
        elif isinstance(element, EmbedElement):
            embed, embed_files = await convert_embed(element, session_info, attachment_prefix=f"embed-{embed_index}")
            embed_index += 1
            embed_units.append((embed, embed_files))
            inline_pending = False

    text_chunks = split_discord_text("\n".join(text_parts)) if text_parts else []
    payloads = []
    text_index = 0
    file_index = 0
    embed_index = 0
    while text_index < len(text_chunks) or file_index < len(files) or embed_index < len(embed_units):
        payload_files = files[file_index : file_index + 10]
        file_index += len(payload_files)
        payload_embeds = []
        while embed_index < len(embed_units) and len(payload_embeds) < 10:
            embed, embed_files = embed_units[embed_index]
            if len(payload_files) + len(embed_files) > 10:
                break
            payload_embeds.append(embed)
            payload_files.extend(embed_files)
            embed_index += 1
        if not payload_embeds and not payload_files and embed_index < len(embed_units):
            embed, embed_files = embed_units[embed_index]
            payload_embeds.append(embed)
            payload_files.extend(embed_files)
            embed_index += 1
        payloads.append(
            DiscordPayload(
                content=text_chunks[text_index] if text_index < len(text_chunks) else None,
                files=payload_files,
                embeds=payload_embeds,
            )
        )
        if text_index < len(text_chunks):
            text_index += 1
    if payloads:
        payloads[-1].action_texts = action_texts
    return payloads


async def execute_discord_payloads(channel, payloads: list[DiscordPayload], reference=None, view=None) -> list:
    """依次发送 Discord 负载，引用仅首条、按钮仅末条。"""
    sent_messages = []
    for index, payload in enumerate(payloads):
        sent_messages.append(
            await channel.send(
                content=payload.content,
                files=payload.files or None,
                embeds=payload.embeds or None,
                reference=reference if index == 0 else None,
                view=view if index == len(payloads) - 1 else None,
            )
        )
    return sent_messages
