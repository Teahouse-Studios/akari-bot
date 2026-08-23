import asyncio
from dataclasses import dataclass

import httpx
import orjson
from khl import Message, MessageTypes, PublicChannel, User

from core.builtins.message.chain import MessageChain, MessageNodes, match_atcode
from core.builtins.message.elements import PlainElement, ImageElement, VoiceElement, MentionElement
from core.builtins.session.context import ContextManager
from core.builtins.session.features import Features
from core.builtins.session.info import SessionInfo
from core.logger import Logger
from .client import bot
from .client import token as kook_token
from .features import features as kook_features
from .info import client_name, target_group_prefix, target_person_prefix, target_guild_prefix

kook_base = "https://www.kookapp.cn"
kook_headers = {"Authorization": f"Bot {kook_token}"}


@dataclass(slots=True)
class KOOKReactionContext:
    """KOOK Reaction 事件中执行回复与删除所需的平台字段。"""

    origin_message_id: str
    emoji: str
    user_id: str


async def call_api(endpoint: str, **params):
    url = f"{kook_base}/api/v3/{endpoint}"
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, data=params, headers=kook_headers)
    try:
        data = orjson.loads(resp.text)
    except orjson.JSONDecodeError as exc:
        raise ValueError({"status_code": resp.status_code, "body": resp.text}) from exc
    if not 200 <= resp.status_code < 300 or not isinstance(data, dict) or data.get("code") not in (None, 0):
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


async def get_guild(session_info: SessionInfo):
    """从 KOOK 频道会话或服务器事件会话取得 Guild。"""
    if session_info.target_from == target_guild_prefix:
        return await bot.client.fetch_guild(session_info.get_common_target_id())
    if session_info.target_from == target_group_prefix:
        channel = await get_channel(session_info)
        if channel:
            return await bot.client.fetch_guild(channel.guild_id)
    return None


class KOOKContextManager(ContextManager):
    context: dict[str, Message | KOOKReactionContext] = {}
    features: Features = kook_features

    @classmethod
    async def check_native_permission(cls, session_info: SessionInfo) -> bool:
        if session_info.target_from == target_person_prefix:
            return True
        ctx = cls.context.get(session_info.session_id)
        if not isinstance(ctx, Message):
            channel = await bot.client.fetch_public_channel(session_info.get_common_target_id())
            author = session_info.get_common_sender_id()
        else:
            Logger.info("Identifying for channel: " + str(ctx.ctx.channel.id))
            channel = await bot.client.fetch_public_channel(ctx.ctx.channel.id)
            author = ctx.author.id
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
    async def send_message(
        cls,
        session_info: SessionInfo,
        message: MessageChain | MessageNodes,
        quote: bool = True,
    ) -> list[str]:
        msg_ids = []
        try:
            return await cls._send_message(
                session_info,
                message,
                quote=quote,
                msg_ids=msg_ids,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            Logger.exception(f"Failed to send KOOK message to {session_info.target_id}: ")
            return msg_ids

    @classmethod
    async def _send_message(
        cls,
        session_info: SessionInfo,
        message: MessageChain | MessageNodes,
        quote: bool = True,
        msg_ids: list[str] | None = None,
    ) -> list[str]:
        # if session_info.session_id not in cls.context:
        #     raise ValueError("Session not found in context")
        raw_ctx = cls.context.get(session_info.session_id)
        ctx = raw_ctx if isinstance(raw_ctx, Message) else None
        reaction_ctx = raw_ctx if isinstance(raw_ctx, KOOKReactionContext) else None
        _channel = None
        if not ctx:
            _channel = await get_channel(session_info)
            if not _channel:
                Logger.warning(f"Channel {session_info.target_id} not found, cannot send message.")
                return []

        if msg_ids is None:
            msg_ids = []
        if isinstance(message, MessageNodes):
            Logger.error("This session does not support message nodes, check if bug exists.")
            return []

        async def send_to_channel(content, message_type: MessageTypes | None = None):
            kwargs = {}
            if message_type is not None:
                kwargs["type"] = message_type
            if reaction_ctx and quote and not msg_ids:
                kwargs["quote"] = reaction_ctx.origin_message_id
            return await _channel.send(content, **kwargs)

        for x in message.as_sendable(session_info):
            if isinstance(x, PlainElement):
                if x.allow_parse:
                    x.text = match_atcode(x.text, client_name, "(met){uid}(met)")
                if ctx:
                    send_ = await ctx.reply(
                        x.text,
                        use_quote=quote and not msg_ids and ctx,
                    )

                else:
                    send_ = await send_to_channel(x.text)
                Logger.info(f"[Bot] -> [{session_info.target_id}]: {x.text}")
                msg_ids.append(str(send_.get("msg_id", "")))
            if isinstance(x, ImageElement):
                image_path = await x.get()
                with open(image_path, "rb") as image:
                    url = await bot.create_asset(image)
                if ctx:
                    send_ = await ctx.reply(
                        url,
                        use_quote=quote and not msg_ids and ctx,
                        type=MessageTypes.IMG,
                    )
                else:
                    send_ = await send_to_channel(url, MessageTypes.IMG)
                Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {str(x.path)}")
                msg_ids.append(str(send_.get("msg_id", "")))
            if isinstance(x, VoiceElement):
                with open(x.path, "rb") as audio:
                    url = await bot.create_asset(audio)
                if ctx:
                    send_ = await ctx.reply(
                        url,
                        use_quote=quote and not msg_ids and ctx,
                        type=MessageTypes.AUDIO,
                    )
                else:
                    send_ = await send_to_channel(url, MessageTypes.AUDIO)
                Logger.info(f"[Bot] -> [{session_info.target_id}]: Voice: {str(x.__dict__)}")
                msg_ids.append(str(send_.get("msg_id", "")))
            if isinstance(x, MentionElement):
                if x.client == client_name and session_info.target_from == target_group_prefix:
                    if ctx:
                        send_ = await ctx.reply(
                            f"(met){x.id}(met)",
                            use_quote=quote and not msg_ids and ctx,
                        )
                    else:
                        send_ = await send_to_channel(f"(met){x.id}(met)")
                    Logger.info(f"[Bot] -> [{session_info.target_id}]: Mention: {x.client}|{str(x.id)}")
                    msg_ids.append(str(send_.get("msg_id", "")))

        return msg_ids

    @classmethod
    async def send_private_msg(
        cls,
        session_info: SessionInfo,
        user_id: str,
        message: MessageChain | MessageNodes,
    ) -> list[str]:
        # KOOK 的私聊场景以用户为频道，get_channel 据此取得 User 对象
        uid = user_id.split("|")[-1]
        try:
            msg_ids = await KOOKContextManager.send_message(
                cls.derive_private_session(session_info, f"{target_person_prefix}|{uid}", target_person_prefix),
                message,
                quote=False,
            )
            # 接口未返回 msg_id 时上游会填入空串，此处过滤以免将失败判定为成功
            return [msg_id for msg_id in msg_ids if msg_id]
        except Exception:
            Logger.exception(f"Failed to send private message to {user_id}: ")
            return []

    @classmethod
    async def delete_message(
        cls, session_info: SessionInfo, message_id: str | list[str], reason: str | None = None
    ) -> None:
        ctx = cls.context.get(session_info.session_id)
        if isinstance(ctx, KOOKReactionContext):
            endpoint = (
                "direct-message/delete-reaction"
                if session_info.target_from == target_person_prefix
                else "message/delete-reaction"
            )
            try:
                await call_api(endpoint, msg_id=ctx.origin_message_id, emoji=ctx.emoji, user_id=ctx.user_id)
                Logger.info(
                    f'Removed reaction "{ctx.emoji}" from message {ctx.origin_message_id} '
                    f"for user {ctx.user_id} in session {session_info.session_id}"
                )
            except Exception:
                Logger.exception(
                    f'Failed to remove reaction "{ctx.emoji}" from message {ctx.origin_message_id} '
                    f"for user {ctx.user_id} in session {session_info.session_id}: "
                )
            return

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
                if session_info.target_from == target_person_prefix:
                    await call_api("direct-message/delete", msg_id=id_)
                else:
                    await call_api("message/delete", msg_id=id_)
                Logger.info(f"Deleted message {id_} in session {session_info.session_id}")
            except Exception:
                Logger.exception(f"Failed to delete message {id_} in session {session_info.session_id}: ")

    @classmethod
    async def grant_permission_group(
        cls,
        session_info: SessionInfo,
        user_id: str | list[str],
        permission_group_id: str | list[str],
        reason: str | None = None,
    ) -> None:
        await cls._edit_permission_groups(session_info, user_id, permission_group_id, grant=True)

    @classmethod
    async def revoke_permission_group(
        cls,
        session_info: SessionInfo,
        user_id: str | list[str],
        permission_group_id: str | list[str],
        reason: str | None = None,
    ) -> None:
        await cls._edit_permission_groups(session_info, user_id, permission_group_id, grant=False)

    @staticmethod
    async def _edit_permission_groups(
        session_info: SessionInfo,
        user_id: str | list[str],
        permission_group_id: str | list[str],
        grant: bool,
    ) -> None:
        user_ids = [user_id] if isinstance(user_id, str) else user_id
        group_ids = [permission_group_id] if isinstance(permission_group_id, str) else permission_group_id
        if not isinstance(user_ids, list) or not isinstance(group_ids, list):
            raise TypeError("User ID and permission group ID must be a list or str")

        guild = await get_guild(session_info)
        if guild is None:
            return
        for uid in user_ids:
            member_id = str(uid).split("|")[-1]
            for group_id in group_ids:
                role_id = str(group_id).split("|")[-1]
                if grant:
                    await guild.grant_role(member_id, role_id)
                else:
                    await guild.revoke_role(member_id, role_id)
        action = "Granted" if grant else "Revoked"
        Logger.info(f"{action} permission groups {group_ids} for members {user_ids} in guild {guild.id}")

    @classmethod
    async def add_reaction(cls, session_info: SessionInfo, message_id: str | list[str], emoji: str) -> None:
        ctx = cls.context.get(session_info.session_id)
        if isinstance(ctx, KOOKReactionContext):
            message_id = ctx.origin_message_id
        if message_id is None:
            Logger.warning(f"KOOK reaction target is unavailable in session {session_info.session_id}.")
            return
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
            if session_info.target_from == target_person_prefix:
                await call_api("direct-message/add-reaction", msg_id=message_id[-1], emoji=emoji)
            else:
                await call_api("message/add-reaction", msg_id=message_id[-1], emoji=emoji)
            Logger.info(f'Added reaction "{emoji}" to message {message_id} in session {session_info.session_id}')
        except Exception:
            Logger.exception(
                f'Failed to add reaction "{emoji}" to message {message_id} in session {session_info.session_id}: '
            )

    @classmethod
    async def remove_reaction(cls, session_info: SessionInfo, message_id: str | list[str], emoji: str) -> None:
        ctx = cls.context.get(session_info.session_id)
        if isinstance(ctx, KOOKReactionContext):
            message_id = ctx.origin_message_id
        if message_id is None:
            Logger.warning(f"KOOK reaction target is unavailable in session {session_info.session_id}.")
            return
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
            if session_info.target_from == target_person_prefix:
                await call_api(
                    "direct-message/delete-reaction",
                    msg_id=message_id[-1],
                    emoji=emoji,
                )
            else:
                await call_api(
                    "message/delete-reaction",
                    msg_id=message_id[-1],
                    emoji=emoji,
                )
            Logger.info(f'Removed reaction "{emoji}" from message {message_id} in session {session_info.session_id}')
        except Exception:
            Logger.exception(
                f'Failed to remove reaction "{emoji}" to message {message_id} in session {session_info.session_id}: '
            )

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
