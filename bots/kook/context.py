from typing import Optional

import httpx
import orjson as json
from khl import Message, MessageTypes, PublicChannel, User

from core.builtins.message.chain import MessageChain, MessageNodes, match_atcode
from core.builtins.message.elements import PlainElement, ImageElement, VoiceElement, MentionElement
from core.builtins.session.context import ContextManager
from core.builtins.session.info import SessionInfo
from core.logger import Logger
from core.utils.image import msgnode2image
from .client import bot
from .client import token as kook_token
from .features import Features
from .info import client_name, target_group_prefix, target_person_prefix

kook_base = "https://www.kookapp.cn"
kook_headers = {
    "Authorization": f"Bot {kook_token}"
}


async def direct_msg_delete(msg_id: str):
    """删除私聊消息"""
    url = f"{kook_base}/api/v3/direct-message/delete"
    params = {"msg_id": msg_id}
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, data=params, headers=kook_headers)
    return json.loads(resp.text)


async def channel_msg_delete(msg_id: str):
    """删除普通消息"""
    url = f"{kook_base}/api/v3/message/delete"
    params = {"msg_id": msg_id}
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, data=params, headers=kook_headers)
    return json.loads(resp.text)


async def get_channel(session_info: SessionInfo) -> PublicChannel | User | None:
    if session_info.target_from == target_group_prefix:
        _channel = await bot.client.fetch_public_channel(session_info.get_common_target_id())
        if not _channel:
            Logger.warning(f"Channel {session_info.target_id} not found, cannot send message.")
            return None
    elif session_info.target_from == target_person_prefix:
        _channel = await bot.client.fetch_user(session_info.get_common_target_id())
        if not _channel:
            Logger.warning(f"Channel {session_info.target_id} not found, cannot send message.")
            return None
    else:
        Logger.warning(f"Unknown target_from: {session_info.target_from}")
        return None
    return _channel


class KOOKContextManager(ContextManager):
    context: dict[str, Message] = {}
    features: Optional[Features] = Features

    @classmethod
    async def check_native_permission(cls, session_info: SessionInfo) -> bool:
        """
        检查会话权限。
        :param session_info: 会话信息
        :return: 是否有权限
        """
        if session_info.session_id not in cls.context:
            channel = await bot.client.fetch_public_channel(session_info.get_common_target_id())
            author = session_info.get_common_sender_id()
        else:
            ctx = cls.context.get(session_info.session_id)
            channel = await bot.client.fetch_public_channel(
                ctx.ctx.channel.id
            )
            author = ctx.author.id
        if channel.name == "PERSON":
            return True
        guild = await bot.client.fetch_guild(channel.guild_id)
        user_roles = (await guild.fetch_user(author)).roles
        guild_roles = await guild.fetch_roles()
        for i in guild_roles:  # 遍历服务器身分组
            if i.id in user_roles and i.has_permission(0):
                return True
        if author == guild.master_id:
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
        ctx = cls.context.get(session_info.session_id)
        _channel = None
        if not ctx:
            _channel = await get_channel(session_info)
            if not _channel:
                Logger.warning(f"Channel {session_info.target_id} not found, cannot send message.")

        msg_ids = []
        if isinstance(message, MessageNodes):
            message = MessageChain.assign(await msgnode2image(message))
        text = []
        images = []
        voices = []
        mentions = []
        for x in message.as_sendable(session_info):
            if isinstance(x, PlainElement):
                x.text = match_atcode(x.text, client_name, "(met){uid}(met)")
                text.append(x.text)
            elif isinstance(x, ImageElement):
                images.append(x)
            elif isinstance(x, VoiceElement):
                voices.append(x)
            elif isinstance(x, MentionElement):
                mentions.append(x)
        if text:
            send_text = "\n".join(text)
            if ctx:
                send_ = await ctx.reply(
                    send_text,
                    quote=(
                        quote if quote and not msg_ids and ctx else None
                    ),
                )

            else:
                send_ = await _channel.send(send_text)
            Logger.info(f"[Bot] -> [{session_info.target_id}]: {send_text}")
            msg_ids.append(str(send_["msg_id"]))

        if images:
            for image in images:
                url = await bot.create_asset(open(await image.get(), "rb"))
                if ctx:
                    send_ = await ctx.reply(
                        url,
                        type=MessageTypes.IMG,
                        quote=(
                            quote if quote and not msg_ids and ctx else None
                        ),
                    )
                else:
                    send_ = await _channel.send(url, type=MessageTypes.IMG, )
                Logger.info(
                    f"[Bot] -> [{session_info.target_id}]: Image: {str(image.path)}"
                )
                msg_ids.append(str(send_["msg_id"]))
        if voices:
            for voice in voices:
                url = await bot.create_asset(open(voice.path, "rb"))
                if ctx:
                    send_ = await ctx.reply(
                        url,
                        type=MessageTypes.AUDIO,
                        quote=(
                            quote if quote and not msg_ids and ctx else None
                        ),
                    )
                else:
                    send_ = await _channel.send(url, type=MessageTypes.AUDIO, )
                Logger.info(
                    f"[Bot] -> [{session_info.target_id}]: Voice: {str(voice.__dict__)}"
                )
                msg_ids.append(str(send_["msg_id"]))
        if mentions:
            for mention in mentions:
                if mention.client == client_name and session_info.target_from == target_group_prefix:
                    if ctx:
                        send_ = await ctx.reply(
                            f"(met){mention.id}(met)",
                            quote=(
                                quote if quote and not msg_ids and ctx else None
                            ),
                        )
                    else:
                        send_ = await _channel.send(
                            f"(met){mention.id}(met)",
                        )
                    Logger.info(
                        f"[Bot] -> [{session_info.target_id}]: Mention: {mention.client}|{str(mention.id)}"
                    )
                    msg_ids.append(str(send_["msg_id"]))

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

        _channel = await get_channel(session_info)
        if not _channel:
            Logger.warning(f"Channel {session_info.target_id} not found, cannot delete message.")
            return
        for id_ in message_id:
            if _channel.type.name == "PERSON":
                await direct_msg_delete(id_)
            else:
                await channel_msg_delete(id_)

    @classmethod
    async def start_typing(cls, session_info: SessionInfo) -> None:
        pass

    @classmethod
    async def end_typing(cls, session_info: SessionInfo) -> None:
        pass

    @classmethod
    async def error_signal(cls, session_info: SessionInfo) -> None:
        pass


class KOOKFetchedContextManager(KOOKContextManager):
    pass
