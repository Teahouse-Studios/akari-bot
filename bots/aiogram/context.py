from datetime import datetime, timedelta

from aiogram import types
from aiogram.types import ChatPermissions, FSInputFile

from bots.aiogram.client import aiogram_bot
from bots.aiogram.features import Features
from bots.aiogram.info import client_name
from core.builtins.message.chain import MessageChain, MessageNodes, match_atcode
from core.builtins.message.elements import PlainElement, ImageElement, VoiceElement, MentionElement
from core.builtins.session.context import ContextManager
from core.builtins.session.info import SessionInfo
from core.logger import Logger
from core.utils.image import msgnode2image, image_split


class AiogramContextManager(ContextManager):
    context: dict[str, types.Message] = {}
    features: Features | None = Features

    @classmethod
    async def check_native_permission(cls, session_info: SessionInfo) -> bool:
        # if session_info.session_id not in cls.context:
        #     raise ValueError("Session not found in context")
        # 这里可以添加权限检查的逻辑
        ctx: types.Message = cls.context.get(session_info.session_id)
        if not ctx:
            chat = await aiogram_bot.get_chat(session_info.get_common_target_id())
        else:
            chat = ctx.chat
        if chat.type == "private":
            return True
        admins = [
            member.user.id for member in await aiogram_bot.get_chat_administrators(chat.id)
        ]
        if ctx.from_user and ctx.from_user.id in admins:
            return True
        return False

    @classmethod
    async def send_message(cls,
                           session_info: SessionInfo,
                           message: MessageChain | MessageNodes,
                           quote: bool = True,
                           enable_parse_message: bool = True,
                           enable_split_image: bool = True,
                           ) -> list[str]:
        # if session_info.session_id not in cls.context:
        #     raise ValueError("Session not found in context")
        msg_ids = []
        buffer_text = []

        async def send_buffer_text():
            nonlocal buffer_text, msg_ids
            if buffer_text:
                send_ = await aiogram_bot.send_message(
                    session_info.get_common_target_id(),
                    "\n".join(buffer_text),
                    reply_to_message_id=(session_info.message_id if quote and not msg_ids and session_info.message_id else None),
                    parse_mode="HTML"
                )
                msg_ids.append(send_.message_id)
                buffer_text = []

        if isinstance(message, MessageNodes):
            message = MessageChain.assign(await msgnode2image(message))

        count = 0
        for x in message.as_sendable(session_info, parse_message=enable_parse_message):
            if isinstance(x, PlainElement):
                if enable_parse_message:
                    x.text = match_atcode(x.text, client_name, "<a href=\"tg://user?id={uid}\">@{uid}</a>")
                buffer_text.append(x.text)
                Logger.info(f"[Bot] -> [{session_info.target_id}]: {x.text}")
                count += 1
            elif isinstance(x, ImageElement):
                await send_buffer_text()
                if enable_split_image:
                    split = await image_split(x)
                    for xs in split:
                        send_ = await aiogram_bot.send_photo(
                            session_info.get_common_target_id(),
                            FSInputFile(await xs.get()),
                            reply_to_message_id=(
                                session_info.message_id if quote and not msg_ids and session_info.message_id
                                else None
                            ),
                        )
                        Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {str(xs)}")
                        msg_ids.append(send_.message_id)
                else:
                    send_ = await aiogram_bot.send_photo(
                        session_info.get_common_target_id(),
                        FSInputFile(await x.get()),
                        reply_to_message_id=(
                            session_info.message_id if quote and not msg_ids and session_info.message_id
                            else None
                        ),
                    )
                    Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {str(x)}")
                    msg_ids.append(send_.message_id)
                count += 1
            elif isinstance(x, VoiceElement):
                await send_buffer_text()
                send_ = await aiogram_bot.send_audio(
                    session_info.get_common_target_id(),
                    FSInputFile(x.path),
                    reply_to_message_id=(
                        session_info.message_id if quote and not msg_ids and session_info.message_id
                        else None
                    ),
                )
                Logger.info(f"[Bot] -> [{session_info.target_id}]: Voice: {str(x)}")
                msg_ids.append(send_.message_id)
                count += 1
            elif isinstance(x, MentionElement):
                if x.client == client_name and session_info.target_from in [
                        f"{client_name}|Group", f"{client_name}|Supergroup"]:
                    buffer_text.append(f"<a href=\"tg://user?id={x.id}\">@{x.id}</a>")
                    Logger.info(f"[Bot] -> [{session_info.target_id}]: Mention: {x.client}|{x.id}")
                count += 1

            if count == len(message):
                await send_buffer_text()
        return msg_ids

    @classmethod
    async def delete_message(cls, session_info: SessionInfo, message_id: str | list[str], reason: str | None = None) -> None:
        # if session_info.session_id not in cls.context:
        #     raise ValueError("Session not found in context")

        if isinstance(message_id, str):
            message_id = [message_id]
        if not isinstance(message_id, list):
            raise TypeError("Message ID must be a list or str")

        for msg_id in message_id:
            try:
                await aiogram_bot.delete_message(
                    chat_id=session_info.get_common_target_id(),
                    message_id=int(msg_id)
                )
                Logger.info(f"Deleted message {msg_id} in session {session_info.session_id}")
            except Exception:
                Logger.exception(f"Failed to delete message {msg_id} in session {session_info.session_id}: ")

    @classmethod
    async def restrict_member(cls, session_info: SessionInfo, user_id: str | list[str], duration: int | None = None, reason: str | None = None) -> None:
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
                    await aiogram_bot.restrict_chat_member(chat_id=session_info.get_common_target_id(),
                                                           user_id=int(x.split("|")[-1]),
                                                           permissions=ChatPermissions(can_send_messages=False,
                                                                                       can_send_media_messages=False,
                                                                                       can_send_polls=False,
                                                                                       can_send_other_messages=False,
                                                                                       can_add_web_page_previews=False),
                                                           until_date=until_date)
                    Logger.info(
                        f"Restricted member {x}{
                            f" ({duration}s)" if duration else " "} in group {
                            session_info.target_id}")
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
                    await aiogram_bot.restrict_chat_member(chat_id=session_info.get_common_target_id(),
                                                           user_id=int(x.split("|")[-1]),
                                                           permissions=ChatPermissions(can_send_messages=True,
                                                                                       can_send_media_messages=True,
                                                                                       can_send_polls=True,
                                                                                       can_send_other_messages=True,
                                                                                       can_add_web_page_previews=True))
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
                    await aiogram_bot.ban_chat_member(chat_id=session_info.get_common_target_id(),
                                                      user_id=int(x.split("|")[-1]))
                    await aiogram_bot.unban_chat_member(chat_id=session_info.get_common_target_id(),
                                                        user_id=int(x.split("|")[-1]))
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
                    await aiogram_bot.ban_chat_member(chat_id=session_info.get_common_target_id(),
                                                      user_id=int(x.split("|")[-1]))
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
                    await aiogram_bot.unban_chat_member(chat_id=session_info.get_common_target_id(),
                                                        user_id=int(x.split("|")[-1]))
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


class AiogramFetchedContextManager(AiogramContextManager):
    pass
