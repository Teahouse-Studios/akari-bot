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
from core.builtins.session.event_types import EventName
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
class EventInfo:
    """可跨进程序列化的平台事件上下文。"""

    event_name: EventName
    data: dict = field(factory=dict)
    target_id: str | None = None
    target_from: str | None = None
    client_name: str | None = None
    sender_id: str | None = None
    sender_from: str | None = None
    target_union_info: TargetUnionInfo | None = None
    sender_union_info: SenderUnionInfo | None = None
    target_union_id: str | None = None
    sender_union_id: str | None = None
    prefixes: list[str] = field(factory=list)

    @classmethod
    async def assign(
        cls,
        event_name: EventName,
        data: dict | None = None,
        target_id: str | None = None,
        target_from: str | None = None,
        client_name: str | None = None,
        sender_id: str | None = None,
        sender_from: str | None = None,
        create: bool = True,
    ) -> Self:
        if target_id and target_from is None:
            target_from = Alive.determine_target_from(target_id)
        if target_from and not client_name:
            client_name = Alive.determine_client(target_from)
        if sender_id and sender_from is None:
            sender_from = Alive.determine_sender_from(sender_id)

        target_union_info, sender_union_info = await asyncio.gather(
            TargetUnionInfo.get_by_target_id(target_id, create) if target_id else _none(),
            SenderUnionInfo.get_by_sender_id(sender_id, create) if sender_id else _none(),
        )
        if target_id and target_union_info is None:
            raise ValueError(f"TargetUnionInfo not found for target_id: {target_id}")

        prefixes = cls._resolve_prefixes(target_union_info)
        return cls(
            event_name=event_name,
            data=data or {},
            target_id=target_id,
            target_from=target_from,
            client_name=client_name,
            sender_id=sender_id,
            sender_from=sender_from,
            target_union_info=target_union_info,
            sender_union_info=sender_union_info,
            target_union_id=target_union_info.union_id if target_union_info else None,
            sender_union_id=sender_union_info.union_id if sender_union_info else None,
            prefixes=prefixes,
        )

    @staticmethod
    def _resolve_prefixes(target_union_info: TargetUnionInfo | None) -> list[str]:
        custom_prefixes = target_union_info.target_data.get("command_prefix", []) if target_union_info else []
        if isinstance(custom_prefixes, str):
            custom_prefixes = [custom_prefixes]
        return list(dict.fromkeys([*custom_prefixes, *command_prefix]))

    async def refresh_info(self) -> Self:
        """反序列化后从数据库恢复 union 对象及场景前缀。"""
        target_union_info, sender_union_info = await asyncio.gather(
            TargetUnionInfo.get_by_target_id(self.target_id, create=False) if self.target_id else _none(),
            SenderUnionInfo.get_by_sender_id(self.sender_id, create=False) if self.sender_id else _none(),
        )
        if self.target_id and target_union_info is None:
            raise ValueError(f"TargetUnionInfo not found for target_id: {self.target_id}")
        self.target_union_info = target_union_info
        self.sender_union_info = sender_union_info
        self.target_union_id = target_union_info.union_id if target_union_info else None
        self.sender_union_id = sender_union_info.union_id if sender_union_info else None
        self.prefixes = self._resolve_prefixes(target_union_info)
        return self


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
    support_delete: bool = False
    support_manage: bool = False
    support_permission_group: bool = False
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
    # 平台消息入口额外声明的前缀（如 Discord Slash、QQ 官方的 ``/``）。
    # refresh_info() 会刷新数据库中的自定义前缀，但必须保留这一组入口能力。
    platform_prefixes: list[str] = field(factory=list)
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
        platform_prefixes = list(prefixes) if prefixes is not None else []
        custom_prefixes = target_union_info.target_data.get("command_prefix", [])
        if isinstance(custom_prefixes, str):
            custom_prefixes = [custom_prefixes]
        prefixes = (
            list(dict.fromkeys([*platform_prefixes, *custom_prefixes, *command_prefix])) if prefixes is not None else []
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
            superuser=sender_union_info.superuser if sender_union_info else False,
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
            platform_prefixes=platform_prefixes,
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
        """从数据库同步会影响当前消息解析的 Union 状态。"""
        # SessionInfo 在 bot 进程构造后才经队列抵达 server；这段时间内权限、静音、
        # 语言或命令前缀都可能被其它消息修改。只替换 ORM 对象而保留派生字段，会让
        # parser 继续按入队时的旧状态执行。
        sender_union_info, target_union_info = await asyncio.gather(
            SenderUnionInfo.get_by_sender_id(self.sender_id, create=False) if self.sender_id else _none(),
            TargetUnionInfo.get_by_target_id(self.target_id, create=False) if self.target_id else _none(),
        )
        # assign() 已在平台进程为入站消息建立两侧映射。消息排队期间若管理员删除了
        # 对应 Union，刷新时绝不能再创建一套默认状态继续执行：那会复活已删除身份，
        # 并可能绕过原 Union 上的封禁、静音或模块配置。
        if self.sender_id and sender_union_info is None:
            raise ValueError(f"SenderUnionInfo not found for sender_id: {self.sender_id}")
        if self.target_id and target_union_info is None:
            raise ValueError(f"TargetUnionInfo not found for target_id: {self.target_id}")
        self.sender_union_info = sender_union_info
        self.sender_union_id = sender_union_info.union_id if sender_union_info else None
        self.superuser = sender_union_info.superuser if sender_union_info else False
        self.petal = sender_union_info.petal if sender_union_info else None
        self.target_union_info = target_union_info
        self.target_union_id = target_union_info.union_id
        self.banned_users = target_union_info.banned_users
        self.custom_admins = target_union_info.custom_admins
        self.muted = target_union_info.muted
        self.locale = Locale(target_union_info.locale)
        self.bot_name = self.locale.t("bot_name")
        self._tz_offset = target_union_info.target_data.get("timezone_offset", CoreConfig.timezone_offset)
        self.timezone_offset = parse_time_string(self._tz_offset)
        custom_prefixes = target_union_info.target_data.get("command_prefix", [])
        if isinstance(custom_prefixes, str):
            custom_prefixes = [custom_prefixes]
        self.prefixes = list(dict.fromkeys([*self.platform_prefixes, *custom_prefixes, *command_prefix]))
        from core.loader import ModulesManager

        enabled_modules = []
        for module_name in target_union_info.modules or []:
            related_names = ModulesManager.get_module_and_alias_first_words(module_name) or [module_name]
            enabled_modules.extend(name for name in related_names if name not in enabled_modules)
        self.enabled_modules = enabled_modules
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


__all__ = ["EventInfo", "SessionInfo", "FetchedSessionInfo", "ModuleHookContext"]
