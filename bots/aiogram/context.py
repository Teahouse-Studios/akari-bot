from typing import Optional

from aiogram import types
from aiogram.types import FSInputFile

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
    features: Optional[Features] = Features

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
        if isinstance(message, MessageNodes):
            message = MessageChain.assign(await msgnode2image(message))

        for x in message.as_sendable(session_info):
            if isinstance(x, PlainElement):
                x.text = match_atcode(x.text, client_name, "<a href=\"tg://user?id={uid}\">@{uid}</a>")
                send_ = await aiogram_bot.send_message(session_info.get_common_target_id(),
                                                       x.text,
                                                       reply_to_message_id=(
                    session_info.message_id if quote and not msg_ids and session_info.message_id
                    else None
                ), parse_mode="HTML"
                )
                Logger.info(f"[Bot] -> [{session_info.target_id}]: {x.text}")
                msg_ids.append(send_.message_id)
            elif isinstance(x, ImageElement):
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
            elif isinstance(x, VoiceElement):
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
            elif isinstance(x, MentionElement):
                if x.client == client_name and session_info.target_from in [
                        f"{client_name}|Group", f"{client_name}|Supergroup"]:
                    send_ = await aiogram_bot.send_message(
                        session_info.get_common_target_id(),
                        f"<a href=\"tg://user?id={x.id}\">@{x.id}</a>",
                        reply_to_message_id=(
                            session_info.message_id if quote and not msg_ids and session_info.message_id else None),
                        parse_mode="HTML"
                    )
                    Logger.info(f"[Bot] -> [{session_info.target_id}]: Mention: {x.client}|{x.id}")
                    msg_ids.append(send_.message_id)

        return msg_ids

    @classmethod
    async def delete_message(cls, session_info: SessionInfo, message_id: list[str]) -> None:
        # if session_info.session_id not in cls.context:
        #     raise ValueError("Session not found in context")

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
