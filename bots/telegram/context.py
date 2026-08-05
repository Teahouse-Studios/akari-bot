from datetime import datetime, timedelta

from aiogram import types
from aiogram.types import ChatPermissions

from bots.telegram.buttons import build_telegram_button_markup, get_telegram_context_chat_and_user
from bots.telegram.action_text import can_use_inline_action_text
from bots.telegram.client import aiogram_bot
from bots.telegram.features import features as telegram_features
from bots.telegram.info import client_name
from bots.telegram.message_builder import (
    build_telegram_operations,
    collect_telegram_content,
    execute_telegram_operations,
)
from core.builtins.message.chain import MessageChain, MessageNodes
from core.builtins.session.context import ContextManager
from core.builtins.session.features import Features
from core.builtins.session.info import SessionInfo
from core.logger import Logger
from core.utils.button_runtime import get_session_button_data


class TelegramContextManager(ContextManager):
    context: dict[str, types.Message | types.CallbackQuery] = {}
    features: Features = telegram_features

    @classmethod
    async def check_native_permission(cls, session_info: SessionInfo) -> bool:
        # if session_info.session_id not in cls.context:
        #     raise ValueError("Session not found in context")
        # 这里可以添加权限检查的逻辑
        ctx: types.Message | types.CallbackQuery | None = cls.context.get(session_info.session_id)
        if not ctx:
            chat = await aiogram_bot.get_chat(session_info.get_common_target_id())
            user_id = int(session_info.sender_id.split("|")[-1])
        else:
            chat, user = get_telegram_context_chat_and_user(ctx)
            user_id = user.id if user else None
        if chat.type == "private":
            return True
        admins = [member.user.id for member in await aiogram_bot.get_chat_administrators(chat.id)]
        return user_id in admins

    @classmethod
    async def send_message(
        cls,
        session_info: SessionInfo,
        message: MessageChain | MessageNodes,
        quote: bool = True,
        enable_parse_message: bool = True,
        enable_split_image: bool = True,
    ) -> list[str]:
        if isinstance(message, MessageNodes):
            Logger.error("This session does not support message nodes, check if bug exists.")
            return []

        content = await collect_telegram_content(
            session_info,
            message,
            enable_parse_message=enable_parse_message,
            enable_split_image=enable_split_image,
        )
        button_data = get_session_button_data(session_info)
        supports_inline_queries = True
        if content.action_texts:
            try:
                supports_inline_queries = can_use_inline_action_text(
                    session_info.target_from,
                    bool((await aiogram_bot.me()).supports_inline_queries),
                )
            except Exception:
                Logger.exception("Failed to detect Telegram Inline Mode support, using copy buttons: ")
                supports_inline_queries = False
        markup = build_telegram_button_markup(
            button_data,
            session_info.sender_id,
            action_texts=content.action_texts,
            supports_inline_queries=supports_inline_queries,
        )
        operations = build_telegram_operations(content, reply_markup=markup)
        reply_id = int(session_info.message_id) if quote and session_info.message_id else None
        sent_messages = await execute_telegram_operations(
            aiogram_bot,
            session_info.get_common_target_id(),
            operations,
            reply_to_message_id=reply_id,
            reply_markup=markup,
        )
        for sent in sent_messages:
            Logger.info(f"[Bot] -> [{session_info.target_id}]: Aggregated Telegram message {sent.message_id}")
        return [str(sent.message_id) for sent in sent_messages]

    @classmethod
    async def send_private_msg(
        cls,
        session_info: SessionInfo,
        user_id: str,
        message: MessageChain | MessageNodes,
        enable_parse_message: bool = True,
        enable_split_image: bool = True,
    ) -> list[str]:
        # Telegram 中用户的私聊 chat_id 即其用户 ID，可直接作为私聊场景发送
        uid = user_id.split("|")[-1]
        try:
            msg_ids = await TelegramContextManager.send_message(
                cls.derive_private_session(session_info, f"{client_name}|Private|{uid}", f"{client_name}|Private"),
                message,
                quote=False,
                enable_parse_message=enable_parse_message,
                enable_split_image=enable_split_image,
            )
            return [str(msg_id) for msg_id in msg_ids]
        except Exception:
            # 对方未曾主动私聊机器人时 aiogram 会抛出异常，此处一律视为发送失败
            Logger.exception(f"Failed to send private message to {user_id}: ")
            return []

    @classmethod
    async def delete_message(
        cls, session_info: SessionInfo, message_id: str | list[str], reason: str | None = None
    ) -> None:
        # if session_info.session_id not in cls.context:
        #     raise ValueError("Session not found in context")

        if isinstance(message_id, str):
            message_id = [message_id]
        if not isinstance(message_id, list):
            raise TypeError("Message ID must be a list or str")

        for msg_id in message_id:
            try:
                await aiogram_bot.delete_message(chat_id=session_info.get_common_target_id(), message_id=int(msg_id))
                Logger.info(f"Deleted message {msg_id} in session {session_info.session_id}")
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

        until_date = None
        if duration:
            until_date = datetime.now() + timedelta(seconds=duration)
        if session_info.target_from != f"{client_name}|Private":
            for x in user_id:
                try:
                    await aiogram_bot.restrict_chat_member(
                        chat_id=session_info.get_common_target_id(),
                        user_id=int(x.split("|")[-1]),
                        permissions=ChatPermissions(
                            can_send_messages=False,
                            can_send_media_messages=False,
                            can_send_polls=False,
                            can_send_other_messages=False,
                            can_add_web_page_previews=False,
                        ),
                        until_date=until_date,
                    )
                    Logger.info(
                        f"Restricted member {x}{f' ({duration}s)' if duration else ' '} in group {
                            session_info.target_id
                        }"
                    )
                except Exception:
                    Logger.exception(f"Failed to restrict member {x} in group {session_info.target_id}: ")

    @classmethod
    async def unrestrict_member(cls, session_info: SessionInfo, user_id: str | list[str]) -> None:
        if isinstance(user_id, str):
            user_id = [user_id]
        if not isinstance(user_id, list):
            raise TypeError("User ID must be a list or str")

        if session_info.target_from != f"{client_name}|Private":
            for x in user_id:
                try:
                    await aiogram_bot.restrict_chat_member(
                        chat_id=session_info.get_common_target_id(),
                        user_id=int(x.split("|")[-1]),
                        permissions=ChatPermissions(
                            can_send_messages=True,
                            can_send_media_messages=True,
                            can_send_polls=True,
                            can_send_other_messages=True,
                            can_add_web_page_previews=True,
                        ),
                    )
                    Logger.info(f"Unrestricted member {x} in group {session_info.target_id}")
                except Exception:
                    Logger.exception(f"Failed to unrestrict member {x} in group {session_info.target_id}: ")

    @classmethod
    async def kick_member(cls, session_info: SessionInfo, user_id: str | list[str], reason: str | None = None) -> None:
        if isinstance(user_id, str):
            user_id = [user_id]
        if not isinstance(user_id, list):
            raise TypeError("User ID must be a list or str")

        if session_info.target_from != f"{client_name}|Private":
            for x in user_id:
                try:
                    await aiogram_bot.ban_chat_member(
                        chat_id=session_info.get_common_target_id(), user_id=int(x.split("|")[-1])
                    )
                    await aiogram_bot.unban_chat_member(
                        chat_id=session_info.get_common_target_id(), user_id=int(x.split("|")[-1])
                    )
                    Logger.info(f"Kicked member {x} in group {session_info.target_id}")
                except Exception:
                    Logger.exception(f"Failed to kick member {x} in group {session_info.target_id}: ")

    @classmethod
    async def ban_member(cls, session_info: SessionInfo, user_id: str | list[str], reason: str | None = None) -> None:
        if isinstance(user_id, str):
            user_id = [user_id]
        if not isinstance(user_id, list):
            raise TypeError("User ID must be a list or str")

        if session_info.target_from != f"{client_name}|Private":
            for x in user_id:
                try:
                    await aiogram_bot.ban_chat_member(
                        chat_id=session_info.get_common_target_id(), user_id=int(x.split("|")[-1])
                    )
                    Logger.info(f"Banned member {x} in group {session_info.target_id}")
                except Exception:
                    Logger.exception(f"Failed to ban member {x} in group {session_info.target_id}: ")

    @classmethod
    async def unban_member(cls, session_info: SessionInfo, user_id: str | list[str]) -> None:
        if isinstance(user_id, str):
            user_id = [user_id]
        if not isinstance(user_id, list):
            raise TypeError("User ID must be a list or str")

        if session_info.target_from != f"{client_name}|Private":
            for x in user_id:
                try:
                    await aiogram_bot.unban_chat_member(
                        chat_id=session_info.get_common_target_id(), user_id=int(x.split("|")[-1])
                    )
                    Logger.info(f"Unbanned member {x} in group {session_info.target_id}")
                except Exception:
                    Logger.exception(f"Failed to unban member {x} in group {session_info.target_id}: ")

    @classmethod
    async def start_typing(cls, session_info: SessionInfo) -> None:
        pass

    @classmethod
    async def end_typing(cls, session_info: SessionInfo) -> None:
        pass

    @classmethod
    async def error_signal(cls, session_info: SessionInfo) -> None:
        pass


class TelegramFetchedContextManager(TelegramContextManager):
    pass
