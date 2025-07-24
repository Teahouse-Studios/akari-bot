from __future__ import annotations

import uuid
from datetime import timedelta, datetime
from typing import Optional, List

from attrs import define

from core.builtins.message.chain import MessageChain
from core.builtins.utils import command_prefix
from core.config import Config
from core.database.models import TargetInfo, SenderInfo
from core.i18n import Locale
from core.utils.alive import Alive
from core.utils.message import parse_time_string


@define
class SessionInfo:
    target_id: str
    target_from: str
    client_name: str
    sender_id: Optional[str] = None
    sender_from: Optional[str] = None
    sender_name: Optional[str] = None
    message_id: Optional[str] = None
    reply_id: Optional[str] = None
    messages: Optional[MessageChain] = None
    superuser: bool = False
    support_image: bool = False
    support_voice: bool = False
    support_mention: bool = False
    support_embed: bool = False
    support_forward: bool = False
    support_delete: bool = False
    support_markdown: bool = False
    support_quote: bool = False
    support_rss: bool = False
    support_typing: bool = False
    support_wait: bool = False
    timestamp: Optional[float] = None
    session_id: Optional[str] = None
    target_info: Optional[TargetInfo] = None
    sender_info: Optional[SenderInfo] = None
    custom_admins: Optional[list] = None
    locale: Optional[Locale] = None
    _tz_offset: Optional[str] = None
    timezone_offset: Optional[timedelta] = None
    bot_name: Optional[str] = None
    muted: Optional[bool] = None
    enabled_modules: Optional[list] = None
    petal: Optional[int] = None
    prefixes: List[str] = []
    ctx_slot: Optional[int] = 0
    fetch: bool = False
    require_enable_modules: bool = True
    require_check_dirty_words: bool = False
    use_url_manager: bool = False
    use_url_md_format: bool = False
    force_use_url_manager: bool = False
    running_mention: bool = True
    tmp: Optional[dict[str, str]] = {}

    @classmethod
    async def assign(cls, target_id: str,
                     client_name: Optional[str] = None,
                     target_from: Optional[str] = None,
                     sender_id: Optional[str] = None,
                     sender_from: Optional[str] = None,
                     sender_name: Optional[str] = None,
                     message_id: Optional[str] = None,
                     reply_id: Optional[str] = None,
                     messages: Optional[MessageChain] = None,
                     prefixes: Optional[List[str]] = None,
                     ctx_slot: int = 0,
                     fetch: bool = False,
                     create: bool = True,
                     require_enable_modules: bool = True,
                     require_check_dirty_words: bool = False,
                     use_url_manager: bool = False,
                     use_url_md_format: bool = False,
                     force_use_url_manager: bool = False,
                     running_mention: bool = True,
                     tmp: Optional[dict[str, str]] = None
                     ) -> SessionInfo:

        """
        用于将参数传入SessionInfo对象中。

        :return: SessionInfo对象。
        """
        if target_from is None:
            target_from = Alive.determine_target_from(target_id)
        target_info = await TargetInfo.get_by_target_id(target_id, create)
        if target_info is None:
            raise ValueError(f"TargetInfo not found for target_id: {target_id}")

        sender_info = await SenderInfo.get_by_sender_id(sender_id, create) if sender_id else None
        if sender_from is None and sender_id:
            sender_from = Alive.determine_sender_from(sender_id)
        if not client_name:
            client_name = Alive.determine_client(target_from)
        timestamp = datetime.now().timestamp()
        session_id = str(uuid.uuid4())
        locale = Locale(target_info.locale)
        bot_name = locale.t("bot_name")
        _tz_offset = target_info.target_data.get("tz_offset", Config("timezone_offset", "+8"))
        prefixes = target_info.target_data.get("command_prefix", []) + command_prefix.copy() + (prefixes or [])
        if fetch:
            ctx_slot = 999

        tmp = tmp or {}

        return cls(
            target_id=target_id,
            target_from=target_from,
            client_name=client_name,
            sender_id=sender_id,
            sender_from=sender_from,
            sender_name=sender_name,
            message_id=message_id,
            reply_id=reply_id,
            messages=messages,
            custom_admins=target_info.custom_admins if target_info else [],
            timestamp=timestamp,
            session_id=session_id,
            target_info=target_info,
            sender_info=sender_info,
            locale=locale,
            muted=target_info.muted,
            bot_name=bot_name,
            tz_offset=_tz_offset,
            enabled_modules=target_info.modules,
            timezone_offset=parse_time_string(_tz_offset),
            petal=sender_info.petal if sender_info else None,
            prefixes=prefixes,
            ctx_slot=ctx_slot,
            fetch=fetch,
            require_enable_modules=require_enable_modules,
            require_check_dirty_words=require_check_dirty_words,
            use_url_manager=use_url_manager,
            use_url_md_format=use_url_md_format,
            force_use_url_manager=force_use_url_manager,
            running_mention=running_mention,
            tmp=tmp,

        )

    async def refresh_info(self):
        self.sender_info = await SenderInfo.get_by_sender_id(self.sender_id) if self.sender_id else None
        self.target_info = await TargetInfo.get_by_target_id(self.target_id) if self.target_id else None

    def get_common_target_id(self) -> str:
        return self.target_id.split(self.target_from + "|")[1]

    def get_common_sender_id(self) -> str:
        return self.sender_id.split(self.sender_from + "|")[1]


@define
class FetchedSessionInfo(SessionInfo):
    """
    主动获取的消息会话信息。
    """
    pass


@define
class ModuleHookContext:
    """
    模块任务上下文。主要用于传递模块任务的参数。
    """

    args: dict
    session_info: Optional[SessionInfo] = None


__all__ = ["SessionInfo", "FetchedSessionInfo", "ModuleHookContext"]
