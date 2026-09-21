"""机器人内置模块 - 提供核心的机器人功能接口和会话管理。"""

import asyncio
from typing import Any, Awaitable, Callable

from core.alive import Alive
from core.builtins.message.chain import *
from core.builtins.parser.hooks import OutgoingPayload, ParserHookContext, Stop, dispatch_outgoing_before_send
from core.builtins.session.context import ContextManager
from core.builtins.session.features import Features
from core.builtins.session.info import EventInfo, SessionInfo, FetchedSessionInfo, ModuleHookContext
from core.builtins.session.internal import MessageSession, FetchedMessageSession, normalize_outgoing_chain
from core.builtins.session.lock import ExecutionLockList
from core.builtins.temp import *
from core.config.base import CoreConfig
from core.constants.info import Info
from core.constants.path import PrivateData, data_path
from core.database.models import (
    AnalyticsData,
    UNION_ID_PREFIXES,
    UNION_SCOPE_TARGET,
    TargetUnionBind,
    TargetUnionInfo,
)
from core.exports import add_export
from core.logger import Logger
from core.utils.retired import filter_retired_targets
from core.utils.func import convert_list
from core.utils.session import inject_features

from core.queue.contracts import PlatformAPI, ServerAPI
from core.queue.errors import RpcUnavailableError

enable_analytics = CoreConfig.enable_analytics


class Bot:
    """机器人核心类。"""

    MessageSession = MessageSession

    FetchedMessageSession = FetchedMessageSession

    ModuleHookContext = ModuleHookContext

    # Parser 入口 hook 上下文；控制结果类型可通过 ``ctx.Stop`` 等访问。
    ParserHookContext = ParserHookContext

    EventInfo = EventInfo

    ExecutionLockList = ExecutionLockList

    Info = Info

    Temp = Temp

    PrivateData = PrivateData

    ContextSlots: list[ContextManager] = []

    fetched_session_ctx_slot = 0

    # 平台 SDK 的消息回调不可被 Server 处理耗时阻塞，因此消息以后台任务投递；
    # 显式持有任务既避免异常无人取回，也便于平台关闭时统一取消。
    _message_tasks: set[asyncio.Task[None]] = set()

    base_superuser_list = CoreConfig.base_superuser
    if isinstance(base_superuser_list, str):
        base_superuser_list = [base_superuser_list]

    @classmethod
    async def process_message(cls, session_info: SessionInfo, ctx: Any, features_override: Features | None = None):
        """处理接收到的消息。

        :param session_info: 会话信息对象，包含消息、用户、平台等信息
        :param ctx: 平台特定的上下文对象（如 QQ 机器人实例）
        :param features_override: 可选的功能特性覆盖对象，用于替代平台默认特性
        :raises TypeError: 如果 session_info 不是 SessionInfo 类型
        """
        if not isinstance(session_info, SessionInfo):
            raise TypeError("session_info must be a SessionInfo")

        ctx_manager = cls.ContextSlots[session_info.ctx_slot]

        features = ctx_manager.features if not features_override else features_override

        session_info = inject_features(session_info, features)

        async def _process_msg():
            ctx_manager.add_context(session_info, ctx)
            try:
                await ServerAPI.receive_message(session_info)

                await asyncio.sleep(1)
            finally:
                # 队列异常或任务被取消时也必须释放平台 SDK 消息对象。
                ctx_manager.del_context(session_info)

        task = asyncio.create_task(_process_msg(), name=f"process-message-{session_info.session_id or 'unknown'}")
        cls._message_tasks.add(task)

        def _message_task_done(done: asyncio.Task[None]) -> None:
            cls._message_tasks.discard(done)
            try:
                done.result()
            except asyncio.CancelledError:
                pass
            except Exception:
                Logger.exception(f"Failed to process message {session_info.session_id or 'unknown'} in background.")

        task.add_done_callback(_message_task_done)

    @classmethod
    async def cancel_pending_messages(cls) -> None:
        """取消并等待当前平台仍在投递的消息任务。"""
        tasks = list(cls._message_tasks)
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    @classmethod
    async def process_event(cls, event_info: EventInfo):
        """将平台事件发送到服务器并交给已绑定该事件的模块处理。"""
        if not isinstance(event_info, EventInfo):
            raise TypeError("event_info must be an EventInfo")

        return await ServerAPI.receive_event.submit(event_info)

    @staticmethod
    async def post_global_message(
        message: Chainable,
        session_list: list[FetchedSessionInfo] | None = None,
        **kwargs: dict[str, Any],
    ):
        """
        发送全局消息到所有场景。

        :param message: 消息内容
        :param session_list: 目标会话列表（None 表示所有开启此模块的场景）
        :param kwargs: 其他参数（传递给 post_message）
        """
        await Bot.post_message("*", message=message, session_list=session_list, **kwargs)

    @classmethod
    async def fetch_target(
        cls, target_id: str, sender_id: str | None = None, create: bool = False, is_private: bool = False
    ) -> FetchedSessionInfo | None:
        """根据场景 ID 获取消息会话信息。

        :param target_id: 场景 ID
        :param sender_id: 用户 ID（可选）
        :param create: 如果场景不存在是否创建
        :param is_private: 该场景是否为私聊。主动获取的会话没有平台事件可依据，
                           核心也不掌握各平台对私聊前缀的表达，故须由调用方指明，缺省按非私聊处理
        :return: 抓取的会话信息，或 None（获取失败）
        """
        try:
            Logger.trace(f"Fetching target {target_id}")
            session = await FetchedSessionInfo.assign(
                target_id=target_id, sender_id=sender_id, fetch=True, create=create, is_private=is_private
            )
        except Exception:
            return None

        return session

    @classmethod
    async def fetch_target_list(cls, target_list: list[str], create: bool = False) -> list[FetchedSessionInfo]:
        """
        批量获取多个场景的会话信息。

        :param target_list: 场景 ID 列表
        :param create: 如果场景不存在是否创建
        :return: 成功获取的会话列表
        """
        fetched = []
        for x in target_list:
            if isinstance(x, str):
                x = await cls.fetch_target(x, create=create)
            if isinstance(x, FetchedSessionInfo):
                fetched.append(x)
        return fetched

    @classmethod
    async def resolve_union_targets(cls, target_list: list[str]) -> list[str]:
        """将场景 ID 归一为其所属场景组的 union ID。

        :param target_list: 场景组 ID 或平台场景 ID 的列表，两种写法可以混用。
        :return: 去重后的场景组 ID 列表，保持传入顺序。
        """
        union_ids = []
        for value in target_list:
            if value.startswith(f"{UNION_ID_PREFIXES[UNION_SCOPE_TARGET]}|"):
                # 场景组 ID 自身不是平台场景，不可交给 resolve_union：
                # 其自愈分支会为组 ID 建出一条以自身为平台 ID 的映射行。
                union_id = value
            else:
                union_info = await TargetUnionInfo.resolve_union(value, create=False)
                union_id = union_info.union_id if union_info else None
            if union_id and union_id not in union_ids:
                union_ids.append(union_id)
        return union_ids

    @classmethod
    async def fetch_union_target_list(
        cls, target_list: str | list[str], create: bool = False
    ) -> list[FetchedSessionInfo]:
        """将场景 ID 按场景组展开后，批量获取会话信息。

        :param target_list: 场景组 ID 或平台场景 ID，两种写法可以混用，可一次传入多个。
        :param create: 如果场景不存在是否创建
        :return: 成功获取的会话列表
        """
        union_ids = await cls.resolve_union_targets(convert_list(target_list))
        # 退役客户端停止一切主动推送，与 get_enabled_this_module() 取同一判据
        target_ids = filter_retired_targets(await TargetUnionBind.list_ids(union_ids))
        return await cls.fetch_target_list(target_ids, create=create)

    @staticmethod
    async def group_sessions_by_channel(
        session_list: list[FetchedSessionInfo],
    ) -> list[list[FetchedSessionInfo]]:
        """将待推送的会话按「场景组 + 消息通道」归拢。

        :param session_list: 待推送的会话列表
        :return: 分组后的会话列表，每组内部保持原有顺序
        """
        channel_maps: dict[str, dict[str, int]] = {}
        groups: dict[tuple[str, Any], list[FetchedSessionInfo]] = {}

        for session_ in session_list:
            union_id = session_.target_union_id
            if union_id and union_id not in channel_maps:
                channel_maps[union_id] = await TargetUnionBind.list_channels(union_id)
            channel_id = channel_maps.get(union_id, {}).get(session_.target_id) if union_id else None
            # 查不到通道号即表示该场景没有绑定行，按独立场景处理，不与其它场景归为一组。
            key = (union_id, channel_id) if union_id and channel_id else ("", session_.target_id)
            groups.setdefault(key, []).append(session_)

        return list(groups.values())

    @classmethod
    async def pick_channel_heads(cls, session_list: list[FetchedSessionInfo]) -> list[FetchedSessionInfo]:
        """按消息通道归拢一批会话，取出各通道实际承担发送的那一个。

        :param session_list: 待发送的会话列表。
        :return: 各通道的队首会话，全员掉线的通道不在其中。
        """
        heads = []
        for hops in await cls.group_sessions_by_channel(session_list):
            # 掉线客户端的任务无人认领，换跳也就无从触发，整条通道将不再有消息送达，因此预先将其剔出跳表
            hops = [hop for hop in hops if Alive.is_alive(hop.client_name)]
            if not hops:
                Logger.warning("Every client of this channel is offline, skipped sending message.")
                continue

            head = hops[0]
            head.next_hops = [hop.target_id for hop in hops[1:]]
            heads.append(head)
        return heads

    @classmethod
    async def post_message(
        cls,
        module_name: str,
        message: Chainable,
        session_list: list[FetchedSessionInfo] | None = None,
        **kwargs: dict[str, Any],
    ):
        """发送消息到开启此模块的场景。

        :param module_name: 模块名称（用于权限检查和分析统计，"*" 表示全局）
        :param message: 消息内容，支持字符串或字典
                       如果是字典，键为客户端名称，值为对应的消息内容
                       会使用 "default" 键作为默认消息
        :param session_list: 目标会话列表
                           如果为 None，自动获取开启了该模块的所有场景
        :param kwargs: 其他参数（保留用）
        """
        if session_list is None:
            session_list = await Bot.get_enabled_this_module(module_name)

        # 同一条消息通道仅推送一次，其余会话作为发送失败时的后备
        for session_ in await cls.pick_channel_heads(session_list):
            chain = get_message_chain(session_, message)

            if isinstance(chain, dict):
                if session_.client_name in chain:
                    post_message = chain[session_.client_name]
                else:
                    post_message = chain["default"]
            else:
                post_message = chain

            # 主动推送也要经过与常规发送一致的出站规范化：过滤关键词并拦截敏感信息，
            # 不能依赖客户端在渲染阶段补检，此时内容已越过服务端唯一能看到的检查点。
            post_message = await normalize_outgoing_chain(session_, post_message, False)
            if post_message is None:
                continue

            # 出站策略（如静音场景停止主动发言）与常规发送共用同一 hook 链。
            outgoing_payload = OutgoingPayload(chain=post_message, quote=False)
            stop_send = await dispatch_outgoing_before_send(
                FetchedMessageSession(session_info=session_), outgoing_payload
            )
            if isinstance(stop_send, Stop):
                continue
            # 改写后的最终消息须重新过完整发送规范化，语义同 MessageSession.send_message。
            post_message = await normalize_outgoing_chain(session_, outgoing_payload.chain, False)
            if post_message is None:
                continue

            try:
                await PlatformAPI.post_message.submit(session_, post_message, module_name)
            except RpcUnavailableError:
                # 选择队首之后可能刚好掉线，仍让剩余场景获得投递机会。
                await ServerAPI.post_next_hop.submit(session_.next_hops, post_message, module_name)
                continue

            # 如果启用分析功能，记录统计数据。一条消息通道计为一次推送，因此每组仅记录一条
            if enable_analytics and module_name:
                await AnalyticsData.create(
                    target_id=session_.target_id,
                    sender_id=session_.sender_id,
                    target_union_id=session_.target_union_id,
                    sender_union_id=session_.sender_union_id,
                    command="",
                    module_name=module_name,
                    module_type="schedule",
                )

    postMessage = post_message
    postGlobalMessage = post_global_message

    @classmethod
    async def start_typing(cls, session_info: SessionInfo) -> None:
        """
        在指定会话中显示“正在输入……”状态。

        :param session_info: 会话信息
        :raises TypeError: 如果 session_info 不是 SessionInfo 类型
        """
        if not isinstance(session_info, SessionInfo):
            raise TypeError("session_info must be a SessionInfo")
        await PlatformAPI.start_typing(session_info)

    @classmethod
    async def end_typing(cls, session_info: SessionInfo) -> None:
        """
        结束“正在输入……”状态。

        :param session_info: 会话信息
        :raises TypeError: 如果 session_info 不是 SessionInfo 类型
        """
        if not isinstance(session_info, SessionInfo):
            raise TypeError("session_info must be a SessionInfo")
        await PlatformAPI.end_typing(session_info)

    @classmethod
    def register_context_manager(cls, ctx_manager: Any, fetch_session: bool = False) -> int:
        """
        注册一个上下文管理器（通常是某个通讯平台的实现）。

        :param ctx_manager: 上下文管理器实例（应继承 ContextManager）
        :param fetch_session: 是否将此管理器用于抓取会话
        :return: 该管理器在 ContextSlots 中的索引
        """
        cls.ContextSlots.append(ctx_manager)
        slot_num = len(cls.ContextSlots) - 1

        if fetch_session:
            cls.fetched_session_ctx_slot = slot_num

        return slot_num

    @classmethod
    def register_bot(cls, client_name: str | None = None, private_data_path: str | None = None):
        """注册机器人实例。

        :param client_name: 客户端名称（如 "qq"、"discord" 等）
        :param private_data_path: 私有资源文件夹路径
                                  如果为 None，自动使用 `data/private/{client_name}` 路径
        """
        if private_data_path:
            PrivateData.set(private_data_path)
        else:
            PrivateData.set(data_path / "private" / client_name.lower())

        Info.client_name = client_name

    @classmethod
    async def send_direct_message(
        cls,
        target: SessionInfo,
        message: Chainable,
        disable_secret_check: bool = False,
    ):
        """
        发送直接消息到场景。

        :param target: 会话信息或场景 ID
        :param message: 消息内容
        :param disable_secret_check: 是否禁用敏感内容检查
        """
        if isinstance(target, str):
            target = await cls.fetch_target(target)

        if isinstance(target, (SessionInfo, FetchedSessionInfo)):
            target = await FetchedMessageSession.from_session_info(target)

        if isinstance(target, (FetchedMessageSession, MessageSession)):
            ...

        if not target:
            raise ValueError("Target not found.")

        message = get_message_chain(target.session_info, message)

        await target.send_direct_message(
            message_chain=message,
            disable_secret_check=disable_secret_check,
        )

    @classmethod
    async def send_direct_message_to_union_target(
        cls,
        union_id: str | list[str],
        message: Chainable | Callable[[FetchedSessionInfo], Awaitable[Chainable | None]],
        disable_secret_check: bool = False,
    ) -> None:
        """向一个场景组绑定的会话发送消息，同一条消息通道只发一次。

        :param union_id: 场景组的 union ID，可一次传入多个。
        :param message: 消息内容，或接受队首会话、返回消息内容的异步工厂，工厂返回 None 表示不发送。
        :param disable_secret_check: 是否禁用敏感内容检查。
        """
        # 退役客户端停止一切主动推送，滤除与场景组展开一并由 fetch_union_target_list 承担
        for session in await cls.pick_channel_heads(await cls.fetch_union_target_list(union_id)):
            # 消息链类型均无 __call__，可据此与消息工厂相区分
            chain = await message(session) if callable(message) else message
            if chain is None:
                continue
            await cls.send_direct_message(
                session,
                chain,
                disable_secret_check=disable_secret_check,
            )

    @classmethod
    async def send_private_message(
        cls,
        session_info: SessionInfo,
        message: Chainable,
        user_id: str | None = None,
    ) -> list[str]:
        """向指定用户单独发送私聊消息。

        :param session_info: 会话信息
        :param message: 消息内容
        :param user_id: 目标用户 ID（带平台前缀），留空则发给该会话的用户
        :return: 消息 ID 列表，为空表示发送失败
        :raises TypeError: 如果 session_info 不是 SessionInfo 类型
        """
        if not isinstance(session_info, SessionInfo):
            raise TypeError("session_info must be a SessionInfo")

        user_id = user_id or session_info.sender_id
        if not user_id:
            return []

        # 平台不支持私信时无需经过队列，直接判定失败
        if not session_info.support_private_msg:
            Logger.warning(f"Client {session_info.client_name} does not support private message.")
            return []

        # 复用 MessageSession 的发送链路，确保关键词过滤与敏感信息检查同样生效
        session = FetchedMessageSession(session_info=session_info)
        return await session.send_private_message(message, user_id=user_id)

    @classmethod
    async def get_enabled_this_module(cls, module: str) -> list[FetchedSessionInfo]:
        """
        获取开启了指定模块的所有场景的会话列表。

        :param module: 模块名称
        :return: 开启了该模块的会话列表
        """
        # 从数据库获取开启此模块的所有场景 ID（一个 union 下绑定的全部平台场景都要展开）
        lst = await TargetUnionInfo.get_target_id_list_by_module(module)
        # 退役客户端停止一切主动推送。
        lst = filter_retired_targets(lst)
        fetched = []

        for target_id in lst:
            x = await cls.fetch_target(target_id)
            if isinstance(x, FetchedSessionInfo):
                fetched.append(x)
        return fetched

    class Hook:
        """钩子系统 - 用于在特定事件触发时执行模块代码。"""

        @staticmethod
        async def trigger(
            module_or_hook_name: str,
            session_info: SessionInfo | None = None,
            args=None,
            timeout: float | None = None,
        ) -> Any:
            """触发模块钩子或自定义钩子。

            :param module_or_hook_name: 模块名称或钩子名称
                                      如果包含 `.`，视为自定义钩子名；否则视为模块名
            :param session_info: 会话信息（可选）
            :param args: 传递给钩子的参数字典
            :param timeout: 覆盖订阅默认执行预算；``<=0`` 表示不限时
            :return: 钩子函数的返回值
            :raises ValueError: 如果模块或钩子名称无效
            """
            from core.builtins.hooks import dispatch_module_hook

            return await dispatch_module_hook(
                module_or_hook_name,
                session_info=session_info,
                args=args,
                timeout=timeout,
            )


add_export(Bot)

__all__ = ["Bot"]
