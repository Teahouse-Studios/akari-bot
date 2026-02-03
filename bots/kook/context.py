import httpx
import orjson
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


async def call_api(endpoint: str, **params):
    url = f"{kook_base}/api/v3/{endpoint}"
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, data=params, headers=kook_headers)
    data = orjson.loads(resp.text)
    if not str(resp.status_code).startswith("2"):
        raise ValueError(data)
    return data


async def get_channel(session_info: SessionInfo) -> PublicChannel | User | None:
    if session_info.target_from == target_group_prefix:
        _channel = await bot.client.fetch_public_channel(session_info.get_common_target_id())
        if not _channel:
            return None
    elif session_info.target_from == target_person_prefix:
        _channel = await bot.client.fetch_user(session_info.get_common_target_id())
        if not _channel:
            return None
    else:
        Logger.warning(f"Unknown target_from: {session_info.target_from}")
        return None
    return _channel


class KOOKContextManager(ContextManager):
    context: dict[str, Message] = {}
    features: Features | None = Features

    @classmethod
    async def check_native_permission(cls, session_info: SessionInfo) -> bool:
        if session_info.session_id not in cls.context:
            channel = await bot.client.fetch_public_channel(session_info.get_common_target_id())
            author = session_info.get_common_sender_id()
        else:
            ctx: Message = cls.context.get(session_info.session_id)
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
        ctx: Message = cls.context.get(session_info.session_id)
        _channel = None
        if not ctx:
            _channel = await get_channel(session_info)
            if not _channel:
                Logger.warning(f"Channel {session_info.target_id} not found, cannot send message.")

        msg_ids = []
        if isinstance(message, MessageNodes):
            message = MessageChain.assign(await msgnode2image(message))

        for x in message.as_sendable(session_info, parse_message=enable_parse_message):
            if isinstance(x, PlainElement):
                if enable_parse_message:
                    x.text = match_atcode(x.text, client_name, "(met){uid}(met)")
                if ctx:
                    send_ = await ctx.reply(
                        x.text,
                        use_quote=quote and not msg_ids and ctx,
                    )

                else:
                    send_ = await _channel.send(x.text)
                Logger.info(f"[Bot] -> [{session_info.target_id}]: {x.text}")
                msg_ids.append(str(send_["msg_id"]))
            if isinstance(x, ImageElement):
                url = await bot.create_asset(open(await x.get(), "rb"))
                if ctx:
                    send_ = await ctx.reply(
                        url,
                        use_quote=quote and not msg_ids and ctx,
                        type=MessageTypes.IMG,
                    )
                else:
                    send_ = await _channel.send(url, type=MessageTypes.IMG, )
                Logger.info(
                    f"[Bot] -> [{session_info.target_id}]: Image: {str(x.path)}"
                )
                msg_ids.append(str(send_["msg_id"]))
            if isinstance(x, VoiceElement):
                url = await bot.create_asset(open(x.path, "rb"))
                if ctx:
                    send_ = await ctx.reply(
                        url,
                        use_quote=quote and not msg_ids and ctx,
                        type=MessageTypes.AUDIO,
                    )
                else:
                    send_ = await _channel.send(url, type=MessageTypes.AUDIO, )
                Logger.info(
                    f"[Bot] -> [{session_info.target_id}]: Voice: {str(x.__dict__)}"
                )
                msg_ids.append(str(send_["msg_id"]))
            if isinstance(x, MentionElement):
                if x.client == client_name and session_info.target_from == target_group_prefix:
                    if ctx:
                        send_ = await ctx.reply(
                            f"(met){x.id}(met)",
                            use_quote=quote and not msg_ids and ctx,
                        )
                    else:
                        send_ = await _channel.send(
                            f"(met){x.id}(met)",
                        )
                    Logger.info(
                        f"[Bot] -> [{session_info.target_id}]: Mention: {x.client}|{str(x.id)}"
                    )
                    msg_ids.append(str(send_["msg_id"]))

        return msg_ids

    @classmethod
    async def delete_message(cls, session_info: SessionInfo, message_id: str | list[str], reason: str | None = None) -> None:
        if isinstance(message_id, str):
            message_id = [message_id]
        if not isinstance(message_id, list):
            raise TypeError("Message ID must be a list or str")

        _channel = await get_channel(session_info)
        if not _channel:
            Logger.warning(f"Channel {session_info.target_id} not found, cannot delete message.")
            return
        for id_ in message_id:
            try:
                if _channel.type.name == "PERSON":
                    await call_api("direct-message/delete", msg_id=id_)
                else:
                    await call_api("message/delete", msg_id=id_)
                Logger.info(f"Deleted message {id_} in session {session_info.session_id}")
            except Exception:
                Logger.exception(f"Failed to delete message {id_} in session {session_info.session_id}: ")

    @classmethod
    async def add_reaction(cls, session_info: SessionInfo, message_id: str | list[str], emoji: str) -> None:
        if isinstance(message_id, str):
            message_id = [message_id]
        if not isinstance(message_id, list):
            raise TypeError("Message ID must be a list or str")

        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")

        _channel = await get_channel(session_info)
        if not _channel:
            Logger.warning(f"Channel {session_info.target_id} not found, cannot add reaction.")
            return

        try:
            if _channel.type.name == "PERSON":
                await call_api("direct-message/add-reaction", msg_id=message_id[-1], emoji=emoji)
            else:
                await call_api("message/add-reaction", msg_id=message_id[-1], emoji=emoji)
            Logger.info(f"Added reaction \"{emoji}\" to message {message_id} in session {session_info.session_id}")
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

        _channel = await get_channel(session_info)
        if not _channel:
            Logger.warning(f"Channel {session_info.target_id} not found, cannot add reaction.")
            return

        try:
            if _channel.type.name == "PERSON":
                await call_api("direct-message/delete-reaction", msg_id=message_id[-1], emoji=emoji)
            else:
                await call_api("message/delete-reaction", msg_id=message_id[-1], emoji=emoji)
            Logger.info(f"Added reaction \"{emoji}\" to message {message_id} in session {session_info.session_id}")
        except Exception:
            Logger.exception(f"Failed to remove reaction \"{emoji}\" to message {
                             message_id} in session {session_info.session_id}: ")

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
