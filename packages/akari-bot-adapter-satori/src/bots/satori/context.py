from __future__ import annotations

import asyncio
import mimetypes
from pathlib import Path

from attrs import define
from satori.client import Account
from satori.model import Member

from bots.satori.client import satori_app
from bots.satori.config import SatoriConfig
from bots.satori.features import features as satori_features
from bots.satori.utils import (
    TargetAddress,
    common_id,
    convert_chain_to_elements,
    parse_sender_id,
    parse_target_id,
)
from core.builtins.message.chain import MessageChain, MessageNodes
from core.builtins.message.elements import AudioElement, ImageElement, VideoElement
from core.builtins.session.bot_state import BotState
from core.builtins.session.context import ContextManager
from core.builtins.session.features import Features
from core.builtins.session.info import SessionInfo
from core.logger import Logger
from core.utils.media import resolve_media_base64, resolve_media_path

# 私聊频道由平台分配，主动发送前先换取频道 ID 并缓存，避免每次发信都创建频道。
_private_channels: dict[str, str] = {}

typing_emoji = str(SatoriConfig.satori_typing_emoji or "")
limited_emoji = str(SatoriConfig.satori_limited_emoji or "")
TYPING_MAX_LIFETIME = 60
TYPING_SHUTDOWN_TIMEOUT = 1.0


def select_account(platform: str | None, bot_id: str | None = None) -> Account | None:
    """按平台与机器人账号选择 Satori 账号；无法精确匹配时退回该平台的首个账号。"""
    accounts = list(satori_app.accounts.values())
    if bot_id:
        for account in accounts:
            if str(account.self_id) == bot_id and (platform is None or account.platform == platform):
                return account
    if platform:
        for account in accounts:
            if account.platform == platform:
                return account
        return None
    return accounts[0] if accounts else None


def _guess_mime(path: str) -> str:
    return mimetypes.guess_type(path)[0] or "application/octet-stream"


async def _upload_media(account: Account, element: ImageElement | AudioElement | VideoElement) -> str | None:
    """取得可在消息元素中引用的媒体地址：已可直链的地址原样使用，本地文件优先上传。"""
    if element.path.startswith(("http://", "https://", "data:")):
        return element.path

    media_path = await resolve_media_path(element)
    if media_path is None:
        return None

    try:
        from satori import Upload

        urls = await account.upload_create(Upload(file=Path(media_path)))
        if urls:
            return urls[0]
    except Exception:
        Logger.exception(f"Failed to upload media file {media_path} to Satori server: ")

    encoded = await resolve_media_base64(element)
    if encoded is None:
        return None
    return f"data:{_guess_mime(media_path)};base64,{encoded}"


async def _private_channel_id(account: Account, user_id: str) -> str | None:
    key = f"{account.platform}:{user_id}"
    if key in _private_channels:
        return _private_channels[key]
    try:
        channel = await account.user_channel_create(user_id)
    except Exception:
        Logger.exception(f"Failed to create Satori private channel for {user_id}: ")
        return None
    _private_channels[key] = channel.id
    return channel.id


def _has_admin_role(member: Member) -> bool:
    configured = SatoriConfig.satori_admin_roles or []
    if isinstance(configured, str):
        configured = [configured]
    roles = {str(role).strip().lower() for role in configured if str(role).strip()}
    return any(role.id.lower() in roles or (role.name or "").lower() in roles for role in member.roles)


def _has_role(member: Member, role_name: str) -> bool:
    return any(role.id.lower() == role_name or (role.name or "").lower() == role_name for role in member.roles)


@define
class SatoriContext:
    """入站消息携带的平台上下文。"""

    account: Account
    platform: str
    channel_id: str
    guild_id: str | None
    is_private: bool
    message_id: str | None = None


class SatoriContextManager(ContextManager):
    context: dict[str, SatoriContext] = {}
    features: Features = satori_features
    typing_tasks: dict[str, asyncio.Task[None]] = {}

    @classmethod
    def _address(cls, session_info: SessionInfo, context: SatoriContext | None) -> TargetAddress | None:
        if context is not None:
            return TargetAddress(
                platform=context.platform,
                is_private=context.is_private,
                guild_id=context.guild_id,
                raw_id=context.channel_id,
            )
        return parse_target_id(session_info.target_id)

    @classmethod
    async def _resolve_target(
        cls, session_info: SessionInfo
    ) -> tuple[Account | None, TargetAddress | None, str | None]:
        context = cls.context.get(session_info.session_id)
        address = cls._address(session_info, context)
        if address is None:
            Logger.warning(f"Unable to resolve Satori target from session {session_info.target_id}.")
            return None, None, None
        account = context.account if context is not None else select_account(address.platform, session_info.bot_id)
        if account is None:
            Logger.warning(f"No Satori account available for platform {address.platform!r}.")
            return None, address, None
        if address.is_private:
            channel_id = (
                context.channel_id if context is not None else await _private_channel_id(account, address.raw_id)
            )
        else:
            channel_id = address.raw_id
        return account, address, channel_id

    @classmethod
    async def _guild_target(cls, session_info: SessionInfo) -> tuple[Account | None, TargetAddress | None]:
        context = cls.context.get(session_info.session_id)
        address = cls._address(session_info, context)
        if address is None or address.is_private or not address.guild_id:
            return None, address
        account = context.account if context is not None else select_account(address.platform, session_info.bot_id)
        return account, address

    @classmethod
    async def check_native_permission(cls, session_info: SessionInfo, user_id: str | None = None) -> bool:
        if session_info.is_private:
            return True
        account, address = await cls._guild_target(session_info)
        if account is None or address is None:
            return False
        member_id = common_id(user_id) if user_id else session_info.get_common_sender_id()
        try:
            member = await account.guild_member_get(address.guild_id, member_id)
        except Exception:
            if user_id is None:
                raise
            Logger.exception(f"Failed to check native permission for {user_id} in {session_info.target_id}: ")
            return False
        return _has_admin_role(member)

    @classmethod
    async def check_bot_state(cls, session_info: SessionInfo) -> BotState:
        if session_info.is_private:
            return BotState(
                available=True,
                joined=True,
                is_owner=None,
                is_admin=None,
                can_read_messages=True,
                can_read_all_messages=True,
                can_send_messages=True,
                can_send_proactive_messages=True,
                can_manage_messages=None,
                can_manage_members=None,
                can_restrict_members=None,
                can_react=True,
                can_send_private_messages=True,
            )
        account, address = await cls._guild_target(session_info)
        if account is None or address is None:
            return BotState(available=None, joined=None, error="Satori context is not a group channel")
        bot_id = str(session_info.bot_id or account.self_id)
        try:
            member = await account.guild_member_get(address.guild_id, bot_id)
        except Exception as exc:
            Logger.exception(f"Failed to check Satori bot state in {session_info.target_id}: ")
            return BotState(available=None, joined=None, error=str(exc))
        is_owner = _has_role(member, "owner")
        is_admin = is_owner or _has_admin_role(member)
        return BotState(
            available=True,
            joined=True,
            is_owner=is_owner,
            is_admin=is_admin,
            can_read_messages=True,
            can_read_all_messages=None,
            can_send_messages=True,
            can_send_proactive_messages=True,
            can_manage_messages=is_admin,
            can_manage_members=is_admin,
            can_restrict_members=is_admin,
            can_react=True,
            can_send_private_messages=True,
            permissions={"roles": [role.id for role in member.roles]},
            raw=member.dump(),
        )

    @classmethod
    async def send_message(
        cls,
        session_info: SessionInfo,
        message: MessageChain | MessageNodes,
        quote: bool = True,
    ) -> list[str]:
        if isinstance(message, MessageNodes):
            Logger.warning("Satori adapter does not support message nodes, skipped.")
            return []
        account, address, channel_id = await cls._resolve_target(session_info)
        if account is None or address is None or channel_id is None:
            return []
        try:
            elements = await convert_chain_to_elements(
                session_info,
                message,
                bot_ids={str(account.self_id)},
                upload=lambda element: _upload_media(account, element),
                quote=quote,
            )
        except Exception:
            Logger.exception(f"Failed to convert message for {session_info.target_id}: ")
            return []
        if not elements:
            return []
        try:
            sent = await account.send_message(channel_id, elements)
        except Exception:
            Logger.exception(f"Failed to send message to {session_info.target_id}: ")
            return []
        Logger.info(f"[Bot] -> [{session_info.target_id}]: {' '.join(str(element) for element in elements)}")
        return [item.id for item in sent]

    @classmethod
    async def send_private_msg(
        cls,
        session_info: SessionInfo,
        user_id: str,
        message: MessageChain | MessageNodes,
    ) -> list[str]:
        if isinstance(message, MessageNodes):
            return []
        info = parse_sender_id(user_id)
        if info is None:
            Logger.warning(f"Invalid Satori user id {user_id}, cannot send private message.")
            return []
        platform, member_id = info
        account = select_account(platform)
        if account is None:
            Logger.warning(f"No Satori account available for platform {platform!r}.")
            return []
        try:
            elements = await convert_chain_to_elements(
                session_info,
                message,
                bot_ids={str(account.self_id)},
                upload=lambda element: _upload_media(account, element),
                quote=False,
            )
        except Exception:
            Logger.exception(f"Failed to convert private message for {user_id}: ")
            return []
        if not elements:
            return []
        try:
            sent = await account.send_private_message(member_id, elements)
        except Exception:
            Logger.exception(f"Failed to send private message to {user_id}: ")
            return []
        return [item.id for item in sent]

    @classmethod
    async def delete_message(
        cls, session_info: SessionInfo, message_id: str | list[str], reason: str | None = None
    ) -> None:
        if isinstance(message_id, str):
            message_id = [message_id]
        if not isinstance(message_id, list):
            raise TypeError("Message ID must be a list or str")
        account, _, channel_id = await cls._resolve_target(session_info)
        if account is None or channel_id is None:
            return
        for item in message_id:
            try:
                await account.message_delete(channel_id, str(item))
            except Exception:
                Logger.exception(f"Failed to delete message {item} in {session_info.target_id}: ")

    @classmethod
    async def restrict_member(
        cls, session_info: SessionInfo, user_id: str | list[str], duration: int | None = None, reason: str | None = None
    ) -> None:
        await cls._mute_member(session_info, user_id, duration or 1800)

    @classmethod
    async def unrestrict_member(cls, session_info: SessionInfo, user_id: str | list[str]) -> None:
        await cls._mute_member(session_info, user_id, 0)

    @classmethod
    async def _mute_member(cls, session_info: SessionInfo, user_id: str | list[str], duration: int) -> None:
        if isinstance(user_id, str):
            user_id = [user_id]
        if not isinstance(user_id, list):
            raise TypeError("User ID must be a list or str")
        account, address = await cls._guild_target(session_info)
        if account is None or address is None:
            return
        for item in user_id:
            try:
                await account.guild_member_mute(address.guild_id, common_id(item), duration)
            except Exception:
                Logger.exception(f"Failed to mute member {item} in {session_info.target_id}: ")

    @classmethod
    async def kick_member(cls, session_info: SessionInfo, user_id: str | list[str], reason: str | None = None) -> None:
        await cls._remove_member(session_info, user_id, permanent=False)

    @classmethod
    async def ban_member(cls, session_info: SessionInfo, user_id: str | list[str], reason: str | None = None) -> None:
        await cls._remove_member(session_info, user_id, permanent=True)

    @classmethod
    async def _remove_member(cls, session_info: SessionInfo, user_id: str | list[str], permanent: bool) -> None:
        if isinstance(user_id, str):
            user_id = [user_id]
        if not isinstance(user_id, list):
            raise TypeError("User ID must be a list or str")
        account, address = await cls._guild_target(session_info)
        if account is None or address is None:
            return
        for item in user_id:
            try:
                await account.guild_member_kick(address.guild_id, common_id(item), permanent=permanent)
            except Exception:
                Logger.exception(f"Failed to remove member {item} in {session_info.target_id}: ")

    @classmethod
    async def _resolve_role_id(cls, account: Account, guild_id: str, role_name: str) -> str | None:
        async for role in account.guild_role_list(guild_id):
            if role.id == role_name:
                return role.id
            if role.name and role.name.lower() == role_name.lower():
                return role.id
        return None

    @classmethod
    async def grant_permission_group(
        cls,
        session_info: SessionInfo,
        user_id: str | list[str],
        permission_group_id: str | list[str],
        reason: str | None = None,
    ) -> None:
        await cls._change_permission_group(session_info, user_id, permission_group_id, enable=True)

    @classmethod
    async def revoke_permission_group(
        cls,
        session_info: SessionInfo,
        user_id: str | list[str],
        permission_group_id: str | list[str],
        reason: str | None = None,
    ) -> None:
        await cls._change_permission_group(session_info, user_id, permission_group_id, enable=False)

    @classmethod
    async def _change_permission_group(
        cls,
        session_info: SessionInfo,
        user_id: str | list[str],
        permission_group_id: str | list[str],
        enable: bool,
    ) -> None:
        if isinstance(user_id, str):
            user_id = [user_id]
        if isinstance(permission_group_id, str):
            permission_group_id = [permission_group_id]
        if not isinstance(user_id, list) or not isinstance(permission_group_id, list):
            raise TypeError("User ID and permission group ID must be a list or str")
        account, address = await cls._guild_target(session_info)
        if account is None or address is None:
            return
        for group in permission_group_id:
            role_id = await cls._resolve_role_id(account, address.guild_id, str(group))
            if role_id is None:
                Logger.warning(f"Satori role {group!r} not found in {session_info.target_id}, skipped.")
                continue
            for item in user_id:
                try:
                    if enable:
                        await account.guild_member_role_set(address.guild_id, common_id(item), role_id)
                    else:
                        await account.guild_member_role_unset(address.guild_id, common_id(item), role_id)
                except Exception:
                    Logger.exception(f"Failed to change Satori role {role_id} of {item} in {session_info.target_id}: ")

    @classmethod
    async def add_reaction(cls, session_info: SessionInfo, message_id: str | list[str], emoji: str) -> None:
        await cls._react(session_info, message_id, emoji, add=True)

    @classmethod
    async def remove_reaction(cls, session_info: SessionInfo, message_id: str | list[str], emoji: str) -> None:
        await cls._react(session_info, message_id, emoji, add=False)

    @classmethod
    async def _react(cls, session_info: SessionInfo, message_id: str | list[str], emoji: str, add: bool) -> None:
        if isinstance(message_id, str):
            message_id = [message_id]
        if not isinstance(message_id, list):
            raise TypeError("Message ID must be a list or str")
        if not emoji:
            return
        account, _, channel_id = await cls._resolve_target(session_info)
        if account is None or channel_id is None:
            return
        for item in message_id:
            try:
                if add:
                    await account.reaction_create(channel_id, str(item), str(emoji))
                else:
                    await account.reaction_delete(channel_id, str(item), str(emoji))
            except Exception:
                Logger.exception(f"Failed to change reaction {emoji} on message {item} in {session_info.target_id}: ")

    @classmethod
    async def start_typing(cls, session_info: SessionInfo) -> None:
        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")

        previous = cls.typing_flags.pop(session_info.session_id, None)
        if previous:
            previous.set()
        previous_task = cls.typing_tasks.pop(session_info.session_id, None)
        if previous_task:
            previous_task.cancel()
            await asyncio.gather(previous_task, return_exceptions=True)
        flag = asyncio.Event()
        cls.typing_flags[session_info.session_id] = flag

        async def _typing():
            try:
                async with asyncio.timeout(TYPING_MAX_LIFETIME):
                    Logger.debug(f"Start typing in session: {session_info.session_id}")
                    if session_info.message_id and not session_info.is_private:
                        await cls.add_reaction(session_info, session_info.message_id, typing_emoji)
                    await flag.wait()
            except TimeoutError:
                Logger.debug(f"Typing state expired in session: {session_info.session_id}")
            except Exception:
                Logger.exception(f"Failed to start typing in session {session_info.session_id}: ")
            finally:
                if cls.typing_flags.get(session_info.session_id) is flag:
                    cls.typing_flags.pop(session_info.session_id, None)
                current_task = asyncio.current_task()
                if cls.typing_tasks.get(session_info.session_id) is current_task:
                    cls.typing_tasks.pop(session_info.session_id, None)

        cls.typing_tasks[session_info.session_id] = asyncio.create_task(
            _typing(), name=f"satori-typing-{session_info.session_id}"
        )

    @classmethod
    async def end_typing(cls, session_info: SessionInfo) -> None:
        flag = cls.typing_flags.pop(session_info.session_id, None)
        if flag:
            flag.set()
        task = cls.typing_tasks.pop(session_info.session_id, None)
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        Logger.debug(f"End typing in session: {session_info.session_id}")

    @classmethod
    async def shutdown(cls) -> None:
        """停止所有输入状态任务，供适配器退出时调用。"""
        for flag in tuple(cls.typing_flags.values()):
            flag.set()

        current = asyncio.current_task()
        tasks = {task for task in cls.typing_tasks.values() if task is not current}
        if tasks:
            _, pending = await asyncio.wait(tasks, timeout=TYPING_SHUTDOWN_TIMEOUT)
            for task in pending:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        cls.typing_flags.clear()
        cls.typing_tasks.clear()

    @classmethod
    async def error_signal(cls, session_info: SessionInfo) -> None:
        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")
        if session_info.message_id and not session_info.is_private:
            await cls.add_reaction(session_info, session_info.message_id, limited_emoji)
