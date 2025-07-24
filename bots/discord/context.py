import asyncio
from typing import Optional, List

import discord
from discord import Message

from bots.discord.client import discord_bot
from bots.discord.features import Features
from bots.discord.info import client_name, target_channel_prefix
from bots.discord.utils import get_channel_id, get_sender_id, convert_embed
from core.builtins.message.chain import MessageChain, MessageNodes, match_atcode
from core.builtins.message.elements import PlainElement, ImageElement, VoiceElement, MentionElement, EmbedElement
from core.builtins.session.context import ContextManager
from core.builtins.session.info import SessionInfo
from core.logger import Logger
from core.utils.image import msgnode2image


class DiscordContextManager(ContextManager):
    context: dict[str, Message] = {}
    features: Optional[Features] = Features

    @classmethod
    async def check_native_permission(cls, session_info: SessionInfo) -> bool:
        """
        检查会话权限。
        :param session_info: 会话信息
        :return: 是否有权限
        """
        # if session_info.session_id not in cls.context:
        #     raise ValueError("Session not found in context")
        # 这里可以添加权限检查的逻辑

        ctx = cls.context.get(session_info.session_id)

        Logger.debug(f"Checking permissions for session: {session_info.session_id}")

        if not ctx:
            channel = await discord_bot.fetch_channel(get_channel_id(session_info))
            author = await channel.guild.fetch_member(get_sender_id(session_info))
        else:
            channel = ctx.channel
            author = ctx.author
        try:
            if channel.permissions_for(author).administrator or isinstance(
                channel, discord.DMChannel
            ):
                return True
        except Exception:
            Logger.exception()
        return False

    @classmethod
    async def send_message(cls, session_info: SessionInfo, message: MessageChain | MessageNodes, quote: bool = True,
                           enable_parse_message: bool = True,
                           enable_split_image: bool = True, ) -> List[str]:

        # if session_info.session_id not in cls.context:
        #     raise ValueError("Session not found in context")
        ctx = cls.context.get(session_info.session_id)
        if ctx:
            channel = ctx.channel
        else:
            channel = await discord_bot.fetch_channel(get_channel_id(session_info))
        msg_ids = []

        if isinstance(message, MessageNodes):
            message = MessageChain.assign(await msgnode2image(message))

        text = []
        images = []
        voices = []
        mentions = []
        embeds = []

        for x in message.as_sendable(session_info):
            if isinstance(x, PlainElement):
                x.text = match_atcode(x.text, client_name, "<@{uid}>")
                text.append(x.text)

            elif isinstance(x, ImageElement):
                images.append(x)
            elif isinstance(x, VoiceElement):
                voices.append(x)
            elif isinstance(x, MentionElement):
                mentions.append(x)
            elif isinstance(x, EmbedElement):
                embeds.append(x)

        if text:
            send_text = "\n".join(text)
            send_ = await channel.send(
                send_text,
                reference=(
                    ctx
                    if quote and not msg_ids and ctx
                    else None
                ),
            )
            Logger.info(f"[Bot] -> [{session_info.target_id}]: {send_text}")
            msg_ids.append(str(send_.id))
        if images:
            for img in images:
                send_ = await channel.send(
                    file=discord.File(await img.get()),
                    reference=(ctx
                               if quote and not msg_ids and ctx
                               else None
                               ),
                )
                Logger.info(
                    f"[Bot] -> [{session_info.target_id}]: Image: {str(img)}"
                )
                msg_ids.append(str(send_.id))
        if voices:
            for voice in voices:
                send_ = await channel.send(
                    file=discord.File(voice.path),
                    reference=(ctx
                               if quote and not msg_ids and ctx
                               else None
                               ),
                )
                Logger.info(
                    f"[Bot] -> [{session_info.target_id}]: Voice: {str(voice)}"
                )
                msg_ids.append(str(send_.id))
        if mentions:
            for mention in mentions:

                if mention.client == client_name and session_info.target_from == target_channel_prefix:
                    send_ = await channel.send(
                        f"<@{mention.id}>",
                        reference=(ctx
                                   if quote and not msg_ids and ctx
                                   else None
                                   ),
                    )
                    Logger.info(
                        f"[Bot] -> [{session_info.target_id}]: Mention: {mention.client}|{str(mention.id)}"
                    )
                    msg_ids.append(str(send_.id))
        if embeds:
            for embed in embeds:
                em, files = await convert_embed(embed, session_info)
                send_ = await channel.send(
                    embed=em,
                    reference=(
                        ctx
                        if quote and not msg_ids and ctx
                        else None
                    ),
                    files=files,
                )
                Logger.info(
                    f"[Bot] -> [{session_info.target_id}]: Embed: {str(embed)}"
                )
                msg_ids.append(str(send_.id))
        return msg_ids

    @classmethod
    async def delete_message(cls, session_info: SessionInfo, message_id: list[str]) -> None:
        """
        删除指定会话中的消息。
        :param session_info: 会话信息
        :param message_id: 消息 ID 列表（为最大兼容，请将元素转换为str，若实现需要传入其他类型再在下方另行实现）
        """
        if isinstance(message_id, str):
            message_id = [message_id]
        if not isinstance(message_id, list):
            raise TypeError("Message ID must be a list or str")

        # if session_info.session_id not in cls.context:
        #     raise ValueError("Session not found in context")

        for msg_id in message_id:
            try:
                channel = await discord_bot.fetch_channel(get_channel_id(session_info))
                message = await channel.fetch_message(msg_id)
                if message:
                    await message.delete()
                    Logger.info(f"Deleted message {msg_id} in session {session_info.session_id}")
            except discord.NotFound:
                Logger.warning(f"Message {msg_id} not found in session {session_info.session_id}")
            except Exception as e:
                Logger.error(f"Failed to delete message {msg_id} in session {session_info.session_id}: {e}")

    @classmethod
    async def start_typing(cls, session_info: SessionInfo) -> None:
        """
        开始输入状态
        :param session_info: 会话信息
        """

        async def _typing():
            if session_info.session_id not in cls.context:
                raise ValueError("Session not found in context")

            ctx = cls.context[session_info.session_id]
            if ctx:
                async with ctx.channel.typing() as typing:
                    Logger.debug(f"Start typing in session: {session_info.session_id}")
                    # 这里可以添加开始输入状态的逻辑
                    flag = asyncio.Event()
                    cls.typing_flags[session_info.session_id] = flag
                    await flag.wait()
                    del cls.typing_flags[session_info.session_id]

            # 这里可以添加开始输入状态的逻辑

        asyncio.create_task(_typing())

    @classmethod
    async def end_typing(cls, session_info: SessionInfo) -> None:
        """
        结束输入状态
        :param session_info: 会话信息
        """
        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")
        if session_info.session_id in cls.typing_flags:
            cls.typing_flags[session_info.session_id].set()
            # 这里可以添加结束输入状态的逻辑
            Logger.debug(f"End typing in session: {session_info.session_id}")

    @classmethod
    async def error_signal(cls, session_info: SessionInfo) -> None:
        pass


class DiscordFetchedContextManager(DiscordContextManager):
    pass  # 由于 DiscordContextManager 已具备无 ctx 时主动获取的特性，因此不需要额外实现，此处继承为后续可能的扩展备用
