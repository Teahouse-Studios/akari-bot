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
        """
        检查会话权限。
        :param session_info: 会话信息
        :return: 是否有权限
        """
        # if session_info.session_id not in cls.context:
        #     raise ValueError("Session not found in context")
        # 这里可以添加权限检查的逻辑
        ctx = cls.context.get(session_info.session_id)
        if not ctx:
            chat = await aiogram_bot.get_chat(session_info.get_common_target_id())
        else:
            chat = ctx.chat
        if chat.type == "private":
            return True
        admins = [
            member.user.id for member in await aiogram_bot.get_chat_administrators(chat.id)
        ]
        if ctx.sender in admins:
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

        text = []
        images = []
        voices = []
        mentions = []
        for x in message.as_sendable(session_info):
            if isinstance(x, PlainElement):
                x.text = match_atcode(x.text, client_name, "<a href=\"tg://user?id={uid}\">@{uid}</a>")
                text.append(x.text)
            elif isinstance(x, ImageElement):
                images.append(x)
            elif isinstance(x, VoiceElement):
                voices.append(x)
            elif isinstance(x, MentionElement):
                mentions.append(x)
        if text:
            send_text = "\n".join(text)
            send_ = await aiogram_bot.send_message(session_info.get_common_target_id(),
                                                   send_text,
                                                   reply_to_message_id=(
                                                       session_info.message_id if quote and not msg_ids and session_info.message_id
                                                       else None
            ), parse_mode="HTML"
            )
            Logger.info(f"[Bot] -> [{session_info.target_id}]: {send_text}")
            msg_ids.append(send_.message_id)
        if images:
            if enable_split_image:
                for image in images:
                    split = await image_split(image)
                    for xs in split:
                        send_ = await aiogram_bot.send_photo(
                            session_info.get_common_target_id(),
                            FSInputFile(await xs.get()),
                            reply_to_message_id=(
                                session_info.message_id if quote and not msg_ids and session_info.message_id
                                else None
                            ),
                        )
                        Logger.info(
                            f"[Bot] -> [{session_info.target_id}]: Image: {str(xs)}"
                        )
                        msg_ids.append(send_.message_id)
            else:
                for image in images:
                    send_ = await aiogram_bot.send_photo(
                        session_info.get_common_target_id(),
                        FSInputFile(await image.get()),
                        reply_to_message_id=(
                            session_info.message_id if quote and not msg_ids and session_info.message_id
                            else None
                        ),
                    )
                    Logger.info(
                        f"[Bot] -> [{session_info.target_id}]: Image: {str(image)}"
                    )
                    msg_ids.append(send_.message_id)
        if voices:
            for voice in voices:
                send_ = await aiogram_bot.send_audio(
                    session_info.get_common_target_id(),
                    FSInputFile(voice.path),
                    reply_to_message_id=(
                        session_info.message_id if quote and not msg_ids and session_info.message_id
                        else None
                    ),
                )
                Logger.info(
                    f"[Bot] -> [{session_info.target_id}]: Voice: {str(voice)}"
                )
                msg_ids.append(send_.message_id)
        if mentions:
            for mention in mentions:
                if mention.client == client_name and session_info.target_from in [
                        f"{client_name}|Group", f"{client_name}|Supergroup"]:
                    send_ = await aiogram_bot.send_message(
                        session_info.get_common_target_id(),
                        f"<a href=\"tg://user?id={mention.id}\">@{mention.id}</a>",
                        reply_to_message_id=(
                            session_info.message_id if quote and not msg_ids and session_info.message_id else None),
                        parse_mode="HTML"
                    )
                    Logger.info(f"[Bot] -> [{session_info.target_id}]: Mention: {mention.client}|{mention.id}")
                    msg_ids.append(send_.message_id)

        return msg_ids

    @classmethod
    async def delete_message(cls, session_info: SessionInfo, message_id: list[str]) -> None:
        """
        删除指定会话中的消息。
        :param session_info: 会话信息
        :param message_id: 消息 ID 列表（为最大兼容，请将元素转换为str，若实现需要传入其他类型再在下方另行实现）
        """

        # if session_info.session_id not in cls.context:
        #     raise ValueError("Session not found in context")

        for msg_id in message_id:
            try:
                await aiogram_bot.delete_message(
                    chat_id=session_info.get_common_target_id(),
                    message_id=int(msg_id)
                )
                Logger.info(f"[Bot] -> [{session_info.target_id}]: Deleted message ID {msg_id}")
            except Exception as e:
                Logger.error(f"[Bot] -> [{session_info.target_id}]: Failed to delete message ID {msg_id}: {e}")

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
