import asyncio
from datetime import datetime, timedelta

import discord
from discord import Message

from bots.discord.buttons import build_discord_button_view
from bots.discord.client import discord_bot
from bots.discord.features import features as discord_features
from bots.discord.info import target_channel_prefix, target_dm_channel_prefix
from bots.discord.message_builder import build_discord_payloads, execute_discord_payloads
from bots.discord.utils import get_channel_id, get_sender_id
from core.builtins.message.chain import MessageChain, MessageNodes
from core.builtins.session.context import ContextManager
from core.builtins.session.features import Features
from core.builtins.session.info import SessionInfo
from core.logger import Logger
from core.utils.button_runtime import get_session_button_data


def resolve_discord_reference(ctx, quote: bool):
    """取得 Discord 普通消息或交互所引用的平台消息。"""
    if not quote or ctx is None:
        return None
    if isinstance(ctx, Message):
        return ctx
    return getattr(ctx, "message", None)


class DiscordContextManager(ContextManager):
    context: dict[str, Message | discord.Interaction] = {}
    features: Features = discord_features

    @classmethod
    async def check_native_permission(cls, session_info: SessionInfo) -> bool:
        # if session_info.session_id not in cls.context:
        #     raise ValueError("Session not found in context")
        # 这里可以添加权限检查的逻辑

        ctx: Message | discord.Interaction | None = cls.context.get(session_info.session_id)

        Logger.debug(f"Checking permissions for session: {session_info.session_id}")

        if not ctx:
            channel = await discord_bot.fetch_channel(int(get_channel_id(session_info)))
            author = await channel.guild.fetch_member(int(get_sender_id(session_info)))
        else:
            channel = ctx.channel
            author = ctx.user if hasattr(ctx, "user") else ctx.author
        try:
            if channel.permissions_for(author).administrator or isinstance(channel, discord.DMChannel):
                return True
        except Exception:
            Logger.exception()
        return False

    @classmethod
    async def send_message(
        cls,
        session_info: SessionInfo,
        message: MessageChain | MessageNodes,
        quote: bool = True,
        enable_parse_message: bool = True,
        enable_split_image: bool = True,
    ) -> list[str]:

        # if session_info.session_id not in cls.context:
        #     raise ValueError("Session not found in context")
        ctx: Message | discord.Interaction | None = cls.context.get(session_info.session_id)
        if ctx:
            channel = ctx.channel
        else:
            channel = await discord_bot.fetch_channel(int(get_channel_id(session_info)))

        if isinstance(message, MessageNodes):
            Logger.error("This session does not support message nodes, check if bug exists.")
            return []

        payloads = await build_discord_payloads(session_info, message, enable_parse_message)
        action_texts = payloads[-1].action_texts if payloads else []
        button_data = get_session_button_data(session_info)
        view = build_discord_button_view(
            button_data,
            session_info.sender_id,
            action_texts=action_texts,
            modal_title=session_info.locale.t("message.action_text.modal.title"),
            input_label=session_info.locale.t("message.action_text.modal.input"),
            select_placeholder=session_info.locale.t("message.action_text.select"),
        )
        reference = resolve_discord_reference(ctx, quote)
        sent_messages = await execute_discord_payloads(channel, payloads, reference=reference, view=view)
        for sent in sent_messages:
            Logger.info(f"[Bot] -> [{session_info.target_id}]: Aggregated Discord message {sent.id}")
        return [str(sent.id) for sent in sent_messages]

    @classmethod
    async def send_private_msg(
        cls,
        session_info: SessionInfo,
        user_id: str,
        message: MessageChain | MessageNodes,
        enable_parse_message: bool = True,
        enable_split_image: bool = True,
    ) -> list[str]:
        uid = user_id.split("|")[-1]
        if not uid.isdigit():
            Logger.warning(f"Invalid user id {user_id}, cannot send private message.")
            return []

        try:
            user = await discord_bot.fetch_user(int(uid))
            # 私信频道须先建立才具有 ID，对方关闭私信时 create_dm 会抛出 Forbidden
            dm_channel = user.dm_channel or await user.create_dm()
            # 显式指定基类：Slash 子类只能回应交互，无法向任意频道发送消息
            return await DiscordContextManager.send_message(
                cls.derive_private_session(
                    session_info, f"{target_dm_channel_prefix}|{dm_channel.id}", target_dm_channel_prefix
                ),
                message,
                quote=False,
                enable_parse_message=enable_parse_message,
                enable_split_image=enable_split_image,
            )
        except Exception:
            Logger.exception(f"Failed to send private message to {user_id}: ")
            return []

    @classmethod
    async def delete_message(
        cls, session_info: SessionInfo, message_id: str | list[str], reason: str | None = None
    ) -> None:
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
                    await message.delete(reason=reason)
                    Logger.info(f"Deleted message {msg_id} in session {session_info.session_id}")
            except discord.NotFound:
                Logger.warning(f"Message {msg_id} not found in session {session_info.session_id}")
            except Exception:
                Logger.exception(f"Failed to delete message {msg_id} in session {session_info.session_id}: ")

    @classmethod
    async def restrict_member(
        cls, session_info: SessionInfo, user_id: str | list[str], duration: int | None = None, reason: str | None = None
    ) -> None:
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
                    await member.timeout(until=until_date, reason=reason)
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
    async def kick_member(cls, session_info: SessionInfo, user_id: str | list[str], reason: str | None = None) -> None:
        if isinstance(user_id, str):
            user_id = [user_id]
        if not isinstance(user_id, list):
            raise TypeError("User ID must be a list or str")

        if session_info.target_from == target_channel_prefix:
            for x in user_id:
                try:
                    channel = await discord_bot.fetch_channel(int(get_channel_id(session_info)))
                    member = await channel.guild.fetch_member(int(get_sender_id(session_info)))
                    await member.kick(reason=reason)
                    Logger.info(f"Kicked member {x} in channel {session_info.target_id}")
                except Exception:
                    Logger.exception(f"Failed to kick member {x} in channel {session_info.target_id}: ")

    @classmethod
    async def ban_member(cls, session_info: SessionInfo, user_id: str | list[str], reason: str | None = None) -> None:
        if isinstance(user_id, str):
            user_id = [user_id]
        if not isinstance(user_id, list):
            raise TypeError("User ID must be a list or str")

        if session_info.target_from == target_channel_prefix:
            for x in user_id:
                try:
                    channel = await discord_bot.fetch_channel(int(get_channel_id(session_info)))
                    member = await channel.guild.fetch_member(int(get_sender_id(session_info)))
                    await member.ban(reason=reason)
                    Logger.info(f"Banned member {x} in channel {session_info.target_id}")
                except Exception:
                    Logger.exception(f"Failed to ban member {x} in channel {session_info.target_id}: ")

    @classmethod
    async def unban_member(cls, session_info: SessionInfo, user_id: str | list[str]) -> None:
        if isinstance(user_id, str):
            user_id = [user_id]
        if not isinstance(user_id, list):
            raise TypeError("User ID must be a list or str")

        if session_info.target_from == target_channel_prefix:
            for x in user_id:
                try:
                    channel = await discord_bot.fetch_channel(int(get_channel_id(session_info)))
                    member = await channel.guild.fetch_member(int(get_sender_id(session_info)))
                    await member.unban()
                    Logger.info(f"Unbanned member {x} in channel {session_info.target_id}")
                except Exception:
                    Logger.exception(f"Failed to unban member {x} in channel {session_info.target_id}: ")

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
                    Logger.info(
                        f'Added reaction "{emoji}" to message {message_id} in session {session_info.session_id}'
                    )
                except Exception:
                    Logger.exception(
                        f'Failed to add reaction "{emoji}" to message {message_id} in session {
                            session_info.session_id
                        }: '
                    )

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
                    Logger.info(
                        f'Removed reaction "{emoji}" to message {message_id} in session {session_info.session_id}'
                    )
                except Exception:
                    Logger.exception(
                        f'Failed to remove reaction "{emoji}" to message {message_id} in session {
                            session_info.session_id
                        }: '
                    )

    @classmethod
    async def start_typing(cls, session_info: SessionInfo) -> None:
        async def _typing():
            if session_info.session_id not in cls.context:
                raise ValueError("Session not found in context")

            ctx = cls.context[session_info.session_id]
            if ctx:
                async with ctx.channel.typing():
                    # session_info.tmp["session_typed"] = 'y'
                    Logger.debug(f"Start typing in session: {session_info.session_id}")
                    # 这里可以添加开始输入状态的逻辑
                    # flag = asyncio.Event()
                    # cls.typing_flags[session_info.session_id] = flag
                    # await flag.wait()
                    # del cls.typing_flags[session_info.session_id]

            # 这里可以添加开始输入状态的逻辑

        asyncio.create_task(_typing())

    @classmethod
    async def end_typing(cls, session_info: SessionInfo) -> None:
        # if session_info.session_id not in cls.context:
        #     raise ValueError("Session not found in context")
        if session_info.session_id in cls.typing_flags:
            # cls.typing_flags[session_info.session_id].set()
            # 这里可以添加结束输入状态的逻辑
            Logger.debug(f"End typing in session: {session_info.session_id}")

    @classmethod
    async def error_signal(cls, session_info: SessionInfo) -> None:
        pass


class DiscordFetchedContextManager(DiscordContextManager):
    pass  # 由于 DiscordContextManager 已具备无 ctx 时主动获取的特性，因此不需要额外实现，此处继承为后续可能的扩展备用
