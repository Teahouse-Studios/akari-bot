"""
会话信息模块 - 定义和管理消息会话的信息和上下文。

该模块定义了 SessionInfo 类，用于承载一个消息会话的所有相关信息，
包括场景、用户、平台特性、权限信息等。
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import timedelta, datetime
from typing import Self

from attrs import define, field

from core.alive import Alive
from core.builtins.message.chain import MessageChain
from core.builtins.session.features import Features
from core.builtins.utils import command_prefix
from core.config.base import CoreConfig
from core.constants.default import default_locale
from core.database.models import TargetUnionInfo, SenderUnionInfo
from core.i18n import Locale
from core.utils.func import parse_time_string
from core.utils.session import inject_features


async def _none():
    """
    并发解析时用于占位的空协程，使 gather 的两路返回值位置保持固定。
    """
    return None


@define
class SessionInfo:
    """
    会话信息类 - 承载一个消息会话的完整信息。

    该类使用 attrs 装饰器，存储了一个消息会话所需的所有信息，
    包括场景和用户信息、消息内容、平台特性、权限和配置等。

    属性分类说明:
    - 基本信息: target_id, target_from, client_name, sender_id, sender_from 等
    - 消息信息: message_id, reply_id, messages 等
    - 平台能力: support_* 系列标志
    - 用户权限: superuser, banned_users, custom_admins 等
    - 数据库模型: target_union_info, sender_union_info
    - 系统配置: locale, prefixes, ctx_slot 等
    """

    target_id: str
    target_from: str
    client_name: str
    sender_id: str | None = None
    sender_from: str | None = None
    sender_name: str | None = None
    message_id: str | None = None
    reply_id: str | None = None
    messages: MessageChain | None = None
    superuser: bool = False
    support_image: bool = False
    support_voice: bool = False
    support_mention: bool = False
    support_embed: bool = False
    support_forward: bool = False
    support_delete: bool = False
    support_manage: bool = False
    support_markdown: bool = False
    support_markdown_table: bool = False
    support_reaction: bool = False
    support_quote: bool = False
    support_rss: bool = False
    support_typing: bool = False
    support_wait: bool = False
    support_handle_message_nodes: bool = False
    support_private_msg: bool = False
    support_action_text: bool = False
    support_button: bool = False
    support_markdown_toggle: bool = False
    timestamp: float | None = None
    session_id: str | None = None
    # 场景 union 由 assign() 解析，解析不出即抛错，故此后必定有值；
    # 用户 union 则不同，没有 sender_id 的会话（如主动推送）本就没有它。
    target_union_info: TargetUnionInfo = field(default=None)
    sender_union_info: SenderUnionInfo | None = None
    target_union_id: str = ""
    sender_union_id: str | None = None
    # 本场景在其场景组内的消息通道号，同组同号即现实中的同一个场景，详见 channel_key
    target_channel_id: int = 1
    banned_users: list | None = None
    custom_admins: list | None = None
    # 会话一律经 assign() 建立，其中必定按场景语言赋值；此处的默认值仅用于
    # 反序列化等缺省情形，故声明为非可选，免去各调用点无谓的判空。
    locale: Locale = field(factory=lambda: Locale(default_locale))
    _tz_offset: str | None = None
    timezone_offset: timedelta | None = None
    bot_name: str | None = None
    bot_id: str | None = None
    muted: bool | None = None
    enabled_modules: list | None = None
    petal: int | None = None
    prefixes: list[str] = field(factory=list)
    # 主动推送的下一跳场景 ID 列表：本跳发送失败时，由客户端回调服务端改用列表中的下一个场景重发
    next_hops: list[str] = field(factory=list)
    ctx_slot: int | None = 0
    fetch: bool = False
    # 是否为私聊场景。由平台适配器在构造会话时判定，各平台对「私聊」的表达互不相同
    # （QQ 为 Private、Discord 为 DM 频道、QQ 官方分 C2C 与频道私信等），核心不作推断。
    is_private: bool = False
    require_enable_modules: bool = True
    read_all_messages: bool = True
    require_check_dirty_words: bool = False
    use_url_manager: bool = False
    use_url_md_format: bool = False
    use_running_mention: bool = True
    # 单次处理内的临时数据，assign() 必定赋值，且会被就地写入，故须逐实例新建
    tmp: dict[str, str] = field(factory=dict)

    @classmethod
    async def assign(
        cls,
        target_id: str,
        client_name: str | None = None,
        target_from: str | None = None,
        sender_id: str | None = None,
        bot_id: str | None = None,
        sender_from: str | None = None,
        sender_name: str | None = None,
        message_id: str | None = None,
        reply_id: str | None = None,
        messages: MessageChain | None = None,
        prefixes: list[str] | None = [],  # skipcq
        ctx_slot: int = 0,
        fetch: bool = False,
        is_private: bool = False,
        create: bool = True,
        features: Features | None = None,
        tmp: dict[str, str] | None = None,
    ) -> Self:
        """
        用于将参数传入 SessionInfo 对象中。

        :return: SessionInfo 对象。
        """
        if target_from is None:
            target_from = Alive.determine_target_from(target_id)
        # 场景与用户的 union 解析互不依赖，并发发出可省去一半的往返等待；
        # 主库在远端时这一项按每次往返的网络延迟计。
        target_union_info, sender_union_info = await asyncio.gather(
            TargetUnionInfo.get_by_target_id(target_id, create),
            SenderUnionInfo.get_by_sender_id(sender_id, create) if sender_id else _none(),
        )
        if target_union_info is None:
            raise ValueError(f"TargetUnionInfo not found for target_id: {target_id}")
        if sender_from is None and sender_id:
            sender_from = Alive.determine_sender_from(sender_id)
        if not client_name:
            client_name = Alive.determine_client(target_from)
        timestamp = datetime.now().timestamp()
        session_id = str(uuid.uuid4())
        locale = Locale(target_union_info.locale)
        bot_name = locale.t("bot_name")
        _tz_offset = target_union_info.target_data.get("timezone_offset", CoreConfig.timezone_offset)
        prefixes = (
            (prefixes + (target_union_info.target_data.get("command_prefix", []) + command_prefix.copy()))
            if prefixes is not None
            else []
        )

        tmp = tmp or {}

        _c = cls(
            target_id=target_id,
            target_from=target_from,
            client_name=client_name,
            sender_id=sender_id,
            sender_from=sender_from,
            sender_name=sender_name,
            message_id=message_id,
            reply_id=reply_id,
            bot_id=bot_id,
            messages=messages,
            banned_users=target_union_info.banned_users,
            custom_admins=target_union_info.custom_admins,
            timestamp=timestamp,
            session_id=session_id,
            target_union_info=target_union_info,
            sender_union_info=sender_union_info,
            target_union_id=target_union_info.union_id,
            sender_union_id=sender_union_info.union_id if sender_union_info else None,
            target_channel_id=target_union_info.bind.channel_id if target_union_info.bind else 1,
            locale=locale,
            muted=target_union_info.muted,
            bot_name=bot_name,
            tz_offset=_tz_offset,
            enabled_modules=target_union_info.modules,
            timezone_offset=parse_time_string(_tz_offset),
            petal=sender_union_info.petal if sender_union_info else None,
            prefixes=prefixes,
            ctx_slot=ctx_slot,
            fetch=fetch,
            is_private=is_private,
            tmp=tmp,
        )

        if features:
            _c = inject_features(session=_c, features=features)

        if fetch:
            get_params = Alive.get_infos(client_name)
            if get_params:
                _c.ctx_slot = get_params.get("ctx_slot_index", 999)
                features = get_params.get("features", None)
                if features:
                    _c = inject_features(session=_c, features=features)

        return _c

    async def refresh_info(self):
        # 同 assign()：两次解析互不依赖，并发发出
        sender_union_info, target_union_info = await asyncio.gather(
            SenderUnionInfo.get_by_sender_id(self.sender_id) if self.sender_id else _none(),
            TargetUnionInfo.get_by_target_id(self.target_id) if self.target_id else _none(),
        )
        self.sender_union_info = sender_union_info
        self.sender_union_id = sender_union_info.union_id if sender_union_info else None
        # 场景 union 解析不出时保留原值，置空只会把问题推迟到后续访问处才暴露
        if target_union_info:
            self.target_union_info = target_union_info
            self.target_union_id = target_union_info.union_id
        bind = self.target_union_info.bind if self.target_union_info else None
        self.target_channel_id = bind.channel_id if bind else 1

    def get_common_target_id(self) -> str:
        """
        获取场景的常用 ID。
        """
        return self.target_id.split("|")[-1]

    def get_common_sender_id(self) -> str:
        """
        获取用户的常用 ID。
        """
        if self.sender_id:
            return self.sender_id.split("|")[-1]
        return ""

    @property
    def channel_key(self) -> str:
        """
        现实场景的标识，形如 ``UTID|8B1F...|1``。

        union 只表示若干平台场景共享同一份数据，并不等于它们是现实中的同一个场景；
        组内 ``target_channel_id`` 相同才是，而默认各占一号即默认谁也不与谁合并。
        冷却、游戏状态、等待任务这类「同一个现实场景内共享」的内存态须按此建键：
        只按 union 建键会把仅仅共享配置、实为不同现实场景的双方错误地并作一处。

        :return: union ID 与消息通道号拼成的键。
        """
        return f"{self.target_union_id}|{self.target_channel_id}"

    @property
    def typing_prompt_enabled(self) -> bool:
        """本会话是否应显示「正在输入……」提示。

        :return: 是否显示输入提示；无从得知用户偏好时不显示。
        """
        if not self.sender_union_info:
            return False
        return self.sender_union_info.sender_data.get("typing_prompt", True)

    @property
    def invalid_module_prompt_enabled(self) -> bool:
        """本会话是否应提示所输入的模块不存在。

        :return: 是否发出提示；场景未设置过时默认发出。
        """
        return self.target_union_info.target_data.get("invalid_module_prompt", True)


@define
class FetchedSessionInfo(SessionInfo):
    """
    主动获取的消息会话信息。
    """


@define
class ModuleHookContext:
    """
    模块任务上下文。主要用于传递模块任务的参数。
    """

    args: dict
    session_info: SessionInfo | None = None


__all__ = ["SessionInfo", "FetchedSessionInfo", "ModuleHookContext"]
