import asyncio
from datetime import datetime, timedelta

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
    features: Features | None = Features

    @classmethod
    async def check_native_permission(cls, session_info: SessionInfo) -> bool:
        # if session_info.session_id not in cls.context:
        #     raise ValueError("Session not found in context")
        # 这里可以添加权限检查的逻辑

        ctx: Message = cls.context.get(session_info.session_id)

        Logger.debug(f"Checking permissions for session: {session_info.session_id}")

        if not ctx:
            channel = await discord_bot.fetch_channel(int(get_channel_id(session_info)))
            author = await channel.guild.fetch_member(int(get_sender_id(session_info)))
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
                           enable_split_image: bool = True, ) -> list[str]:

        # if session_info.session_id not in cls.context:
        #     raise ValueError("Session not found in context")
        ctx: Message = cls.context.get(session_info.session_id)
        if ctx:
            channel = ctx.channel
        else:
            channel = await discord_bot.fetch_channel(int(get_channel_id(session_info)))

        if isinstance(message, MessageNodes):
            message = MessageChain.assign(await msgnode2image(message))

        msg_ids = []
        for x in message.as_sendable(session_info, parse_message=enable_parse_message):
            send_ = None
            if isinstance(x, PlainElement):
                if enable_parse_message:
                    x.text = match_atcode(x.text, client_name, "<@{uid}>")
                send_ = await channel.send(
                    x.text,
                    reference=(
                        ctx
                        if quote and not msg_ids and ctx
                        else None
                    ),
                )
                Logger.info(f"[Bot] -> [{session_info.target_id}]: {x.text}")
                msg_ids.append(str(send_.id))
            elif isinstance(x, ImageElement):
                send_ = await channel.send(
                    file=discord.File(await x.get()),
                    reference=(ctx
                               if quote and not msg_ids and ctx
                               else None
                               ),
                )
                Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {str(x)}")
                msg_ids.append(str(send_.id))
            elif isinstance(x, VoiceElement):
                send_ = await channel.send(
                    file=discord.File(x.path),
                    reference=(ctx
                               if quote and not msg_ids and ctx
                               else None
                               ),
                )
                Logger.info(f"[Bot] -> [{session_info.target_id}]: Voice: {str(x)}")
                msg_ids.append(str(send_.id))
            elif isinstance(x, MentionElement):
                if x.client == client_name and session_info.target_from == target_channel_prefix:
                    send_ = await channel.send(
                        f"<@{x.id}>",
                        reference=(ctx
                                   if quote and not msg_ids and ctx
                                   else None
                                   ),
                    )
                    Logger.info(f"[Bot] -> [{session_info.target_id}]: Mention: {x.client}|{str(x.id)}")
                    msg_ids.append(str(send_.id))
            elif isinstance(x, EmbedElement):
                em, files = await convert_embed(x, session_info)
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
                    f"[Bot] -> [{session_info.target_id}]: Embed: {str(x)}"
                )
                msg_ids.append(str(send_.id))

        return msg_ids

    @classmethod
    async def delete_message(cls, session_info: SessionInfo, message_id: str | list[str]) -> None:
        if isinstance(message_id, str):
            message_id = [message_id]
        if not isinstance(message_id, list):
            raise TypeError("Message ID must be a list or str")

        # if session_info.session_id not in cls.context:
        #     raise ValueError("Session not found in context")

        for msg_id in message_id:
            try:
                channel = await discord_bot.fetch_channel(int(get_channel_id(session_info)))
                message = await channel.fetch_message(int(msg_id))
                if message:
                    await message.delete()
                    Logger.info(f"Deleted message {msg_id} in session {session_info.session_id}")
            except discord.NotFound:
                Logger.warning(f"Message {msg_id} not found in session {session_info.session_id}")
            except Exception:
                Logger.exception(f"Failed to delete message {msg_id} in session {session_info.session_id}: ")

    @classmethod
    async def restrict_member(cls, session_info: SessionInfo, user_id: str | list[str], duration: int | None) -> None:
        if isinstance(user_id, str):
            user_id = [user_id]
        if not isinstance(user_id, list):
            raise TypeError("User ID must be a list or str")

        if not duration:
            duration = 1800
        until_date = datetime.now() + timedelta(seconds=duration)
        if session_info.target_from == target_channel_prefix:
            for x in user_id:
                try:
                    channel = await discord_bot.fetch_channel(int(get_channel_id(session_info)))
                    member = await channel.guild.fetch_member(int(get_sender_id(session_info)))
                    await member.timeout(until=until_date)
                    Logger.info(f"Restricted member {x} ({duration}s) in channel {session_info.target_id}")
                except Exception:
                    Logger.exception(f"Failed to restrict member {x} in channel {session_info.target_id}: ")

    @classmethod
    async def unrestrict_member(cls, session_info: SessionInfo, user_id: str | list[str]) -> None:
        if isinstance(user_id, str):
            user_id = [user_id]
        if not isinstance(user_id, list):
            raise TypeError("User ID must be a list or str")

        if session_info.target_from == target_channel_prefix:
            for x in user_id:
                try:
                    channel = await discord_bot.fetch_channel(int(get_channel_id(session_info)))
                    member = await channel.guild.fetch_member(int(get_sender_id(session_info)))
                    await member.timeout(None)
                    Logger.info(f"Unrestricted member {x} in channel {session_info.target_id}")
                except Exception:
                    Logger.exception(f"Failed to unrestrict member {x} in channel {session_info.target_id}: ")

    @classmethod
    async def kick_member(cls, session_info: SessionInfo, user_id: str | list[str], ban: bool = False) -> None:
        if isinstance(user_id, str):
            user_id = [user_id]
        if not isinstance(user_id, list):
            raise TypeError("User ID must be a list or str")

        if session_info.target_from == target_channel_prefix:
            for x in user_id:
                try:
                    channel = await discord_bot.fetch_channel(int(get_channel_id(session_info)))
                    member = await channel.guild.fetch_member(int(get_sender_id(session_info)))
                    if ban:
                        await member.ban()
                    else:
                        await member.kick()
                    Logger.info(f"{"Banned" if ban else "Kicked"} member {x} in channel {session_info.target_id}")
                except Exception:
                    Logger.exception(
                        f"Failed to {
                            "ban" if ban else "kick"} member {x} in channel {
                            session_info.target_id}: ")

    @classmethod
    async def add_reaction(cls, session_info: SessionInfo, message_id: str | list[str], emoji: str) -> None:
        if isinstance(message_id, str):
            message_id = [message_id]
        if not isinstance(message_id, list):
            raise TypeError("Message ID must be a list or str")

        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")

        if c := await discord_bot.fetch_channel(int(get_channel_id(session_info))):
            m = await c.fetch_message(int(message_id[-1]))
            if m:
                try:
                    await m.add_reaction(emoji)
                    Logger.info(f"Added reaction \"{emoji}\" to message {
                                message_id} in session {session_info.session_id}")
                except Exception:
                    Logger.exception(f"Failed to add reaction \"{emoji}\" to message {
                                     message_id} in session {session_info.session_id}: ")

    @classmethod
    async def remove_reaction(cls, session_info: SessionInfo, message_id: str | list[str], emoji: str) -> None:
        if isinstance(message_id, str):
            message_id = [message_id]
        if not isinstance(message_id, list):
            raise TypeError("Message ID must be a list or str")

        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")

        if c := await discord_bot.fetch_channel(int(get_channel_id(session_info))):
            m = await c.fetch_message(int(message_id[-1]))
            if m:
                try:
                    await m.remove_reaction(emoji, discord_bot.user)
                    Logger.info(f"Removed reaction \"{emoji}\" to message {
                                message_id} in session {session_info.session_id}")
                except Exception:
                    Logger.exception(f"Failed to remove reaction \"{emoji}\" to message {
                                     message_id} in session {session_info.session_id}: ")

    @classmethod
    async def start_typing(cls, session_info: SessionInfo) -> None:
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
        # if session_info.session_id not in cls.context:
        #     raise ValueError("Session not found in context")
        if session_info.session_id in cls.typing_flags:
            cls.typing_flags[session_info.session_id].set()
            # 这里可以添加结束输入状态的逻辑
            Logger.debug(f"End typing in session: {session_info.session_id}")

    @classmethod
    async def error_signal(cls, session_info: SessionInfo) -> None:
        pass


class DiscordFetchedContextManager(DiscordContextManager):
    pass  # 由于 DiscordContextManager 已具备无 ctx 时主动获取的特性，因此不需要额外实现，此处继承为后续可能的扩展备用
