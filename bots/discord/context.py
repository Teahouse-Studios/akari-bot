import asyncio
import datetime
import re
import traceback
from typing import Any, Union, Optional, List

import discord
from discord import Message

from bots.discord.client import client
from bots.discord.info import client_name, target_channel_prefix
from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import PlainElement, ImageElement, VoiceElement, MentionElement, EmbedElement
from core.builtins.session.info import SessionInfo
from bots.discord.features import Features
from core.builtins.session.context import ContextManager
from core.logger import Logger


def get_channel_id(session_info: SessionInfo) -> str:
    return session_info.target_id.split(session_info.target_from + "|")[1]


def get_sender_id(session_info: SessionInfo) -> str:
    return session_info.sender_id.split(session_info.sender_from + "|")[1]


async def convert_embed(embed: EmbedElement, session_info: SessionInfo):
    if isinstance(embed, EmbedElement):
        files = []
        embeds = discord.Embed(
            title=session_info.locale.t_str(embed.title) if embed.title else None,
            description=session_info.locale.t_str(embed.description) if embed.description else None,
            color=embed.color if embed.color else None,
            url=embed.url if embed.url else None,
            timestamp=datetime.datetime.fromtimestamp(embed.timestamp) if embed.timestamp else None
        )
        if embed.image:
            upload = discord.File(await embed.image.get(), filename="image.png")
            files.append(upload)
            embeds.set_image(url="attachment://image.png")
        if embed.thumbnail:
            upload = discord.File(await embed.thumbnail.get(), filename="thumbnail.png")
            files.append(upload)
            embeds.set_thumbnail(url="attachment://thumbnail.png")
        if embed.author:
            embeds.set_author(name=session_info.locale.t_str(embed.author))
        if embed.footer:
            embeds.set_footer(text=session_info.locale.t_str(embed.footer))
        if embed.fields:
            for field in embed.fields:
                embeds.add_field(
                    name=session_info.locale.t_str(field.name),
                    value=session_info.locale.t_str(field.value),
                    inline=field.inline
                )
        return embeds, files
    else:
        raise TypeError("Embed must be an instance of EmbedElement")


class DiscordContextManager(ContextManager):
    context: dict[str, Message] = {}
    features: Optional[Features] = Features
    typing_flags: dict[str, asyncio.Event] = {}

    @classmethod
    def add_context(cls, session_info: SessionInfo, context: Message):
        cls.context[session_info.session_id] = context

    @classmethod
    def del_context(cls, session_info: SessionInfo):
        if session_info.session_id in cls.context:
            del cls.context[session_info.session_id]

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

        ctx = cls.context.get(session_info.session_id, None)

        Logger.debug(f"Checking permissions for session: {session_info.session_id}")

        if not ctx:
            channel = await client.fetch_channel(get_channel_id(session_info))
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
            Logger.error(traceback.format_exc())
        return False

    @classmethod
    async def send_message(cls, session_info: SessionInfo, message: Union[MessageChain, str], quote: bool = True,):
        """
        发送消息到指定的会话。
        :param session_info: 会话信息
        :param message: 消息内容，可以是 MessageChain 或字符串
        :param quote: 是否引用消息
        :return: 消息 ID 列表
        """
        if isinstance(message, str):
            message = MessageChain.assign(message)
        if not isinstance(message, MessageChain):
            raise TypeError("Message must be a MessageChain or str")

        # if session_info.session_id not in cls.context:
        #     raise ValueError("Session not found in context")
        ctx = cls.context.get(session_info.session_id)
        if ctx:
            channel = ctx.channel
        else:
            channel = await client.fetch_channel(get_channel_id(session_info))

        count = 0
        msg_ids = []
        for x in message.as_sendable(session_info):
            send_ = None
            if isinstance(x, PlainElement):
                send_ = await channel.send(
                    x.text,
                    reference=(
                        ctx
                        if quote and count == 0 and ctx
                        else None
                    ),
                )
                Logger.info(f"[Bot] -> [{session_info.target_id}]: {x.text}")
            elif isinstance(x, ImageElement):
                send_ = await channel.send(
                    file=discord.File(await x.get()),
                    reference=(ctx
                               if quote and count == 0 and ctx
                               else None
                               ),
                )
                Logger.info(
                    f"[Bot] -> [{session_info.target_id}]: Image: {str(x.__dict__)}"
                )
            elif isinstance(x, VoiceElement):
                send_ = await channel.send(
                    file=discord.File(x.path),
                    reference=(
                        ctx
                        if quote and count == 0 and ctx
                        else None
                    ),
                )
                Logger.info(
                    f"[Bot] -> [{session_info.target_id}]: Voice: {str(x.__dict__)}"
                )
            elif isinstance(x, MentionElement):
                if x.client == client_name and session_info.target_from == target_channel_prefix:
                    send_ = await channel.send(
                        f"<@{x.id}>",
                        reference=(ctx
                                   if quote and count == 0 and ctx
                                   else None
                                   ),
                    )
                    Logger.info(
                        f"[Bot] -> [{session_info.target_id}]: Mention: {x.client}|{str(x.id)}"
                    )
            elif isinstance(x, EmbedElement):
                embeds, files = await convert_embed(x, session_info)
                send_ = await channel.send(
                    embed=embeds,
                    reference=(
                        ctx
                        if quote and count == 0 and ctx
                        else None
                    ),
                    files=files,
                )
                Logger.info(
                    f"[Bot] -> [{session_info.target_id}]: Embed: {str(x.__dict__)}"
                )

            if send_:
                msg_ids.append(str(send_.id))
            count += 1
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

        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")

        for msg_id in message_id:
            try:
                channel = await client.fetch_channel(get_channel_id(session_info))
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
            del cls.typing_flags[session_info.session_id]
        # 这里可以添加结束输入状态的逻辑
        Logger.debug(f"End typing in session: {session_info.session_id}")


class DiscordFetchedContextManager(DiscordContextManager):
    pass
