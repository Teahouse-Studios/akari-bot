"""
机器人内置模块 - 提供核心的机器人功能接口和会话管理。

该模块定义了 Bot 类，作为系统与各种通讯平台的主要接口，
负责消息处理、会话管理、上下文管理等核心功能。
"""

import asyncio
from typing import Any, TYPE_CHECKING

from core.alive import Alive
from core.builtins.message.chain import *
from core.builtins.session.context import ContextManager
from core.builtins.session.features import Features
from core.builtins.session.info import SessionInfo, FetchedSessionInfo, ModuleHookContext
from core.builtins.session.internal import MessageSession, FetchedMessageSession
from core.builtins.session.lock import ExecutionLockList
from core.builtins.temp import *
from core.config.base import CoreConfig
from core.constants.info import Info
from core.constants.path import PrivateAssets, assets_path
from core.database.models import AnalyticsData, TargetUnionBind, TargetUnionInfo
from core.exports import add_export, exports
from core.loader import ModulesManager
from core.logger import Logger
from core.retired import filter_retired_targets
from core.utils.session import inject_features

if TYPE_CHECKING:
    from core.queue.client import JobQueueClient
    from core.queue.server import JobQueueServer

enable_analytics = CoreConfig.enable_analytics


class Bot:
    """
    机器人核心类。

    提供了机器人的主要功能接口，包括消息处理、会话管理、上下文管理、
    模块钩子执行等。作为系统的中心枢纽，协调各个通讯平台客户端和
    核心业务逻辑的交互。
    """

    # ========== 核心类型引用 ==========
    # 消息会话类型 - 用于处理常规消息
    MessageSession = MessageSession

    # 抓取消息会话类型 - 用于主动获取和发送消息
    FetchedMessageSession = FetchedMessageSession

    # 模块钩子上下文类型 - 用于模块钩子函数的参数传递
    ModuleHookContext = ModuleHookContext

    # 执行锁列表 - 防止同一用户并发执行命令
    ExecutionLockList = ExecutionLockList

    # 系统信息 - 包含版本、构建信息等
    Info = Info

    # 临时存储 - 用于会话生命周期内的临时数据
    Temp = Temp

    # 私有资源路径 - 用于存储特定客户端的私有资源
    PrivateAssets = PrivateAssets

    # 上下文管理器列表 - 存储注册的各个通讯平台的上下文管理器
    ContextSlots: list[ContextManager] = []

    # 主动获取消息会话的上下文管理器索引
    fetched_session_ctx_slot = 0

    # 超级用户列表 - 拥有最高权限的用户 ID 列表
    base_superuser_list = CoreConfig.base_superuser
    if isinstance(base_superuser_list, str):
        base_superuser_list = [base_superuser_list]

    @classmethod
    async def process_message(cls, session_info: SessionInfo, ctx: Any, features_override: Features | None = None):
        """
        处理接收到的消息。

        这是消息处理的入口点。将消息会话信息和平台特定的上下文（如对应框架下的消息实例）进行关联，
        然后发送给消息队列处理器进行异步处理。

        :param session_info: 会话信息对象，包含消息、用户、平台等信息
        :param ctx: 平台特定的上下文对象（如 QQ 机器人实例）
        :param features_override: 可选的功能特性覆盖对象，用于替代平台默认特性
        :raises TypeError: 如果 session_info 不是 SessionInfo 类型
        """
        # 验证 session_info 的类型
        if not isinstance(session_info, SessionInfo):
            raise TypeError("session_info must be a SessionInfo")

        # 获取该会话对应的上下文管理器
        ctx_manager = cls.ContextSlots[session_info.ctx_slot]

        # 从上下文管理器获取平台支持的功能特性
        features = ctx_manager.features if not features_override else features_override

        # 将各项功能特性标志设置到会话信息中
        session_info = inject_features(session_info, features)

        async def _process_msg():
            """内部异步处理函数 - 管理消息处理的生命周期"""
            # 添加上下文到管理器（存储 session_id 和对应的上下文对象）
            ctx_manager.add_context(session_info, ctx)

            # 获取消息队列客户端并发送消息给服务器处理
            queue_client: "JobQueueClient" = exports["JobQueueClient"]

            await queue_client.send_message_to_server(session_info)

            # 等待 1 秒后清理上下文（防止删除过快导致的错误）
            await asyncio.sleep(1)

            # 从管理器中删除上下文
            ctx_manager.del_context(session_info)

        # 创建异步任务处理消息
        asyncio.create_task(_process_msg())

    @staticmethod
    async def post_global_message(
        message: Chainable,
        session_list: list[FetchedSessionInfo] | None = None,
        **kwargs: dict[str, Any],
    ):
        """
        发送全局消息到所有会话。

        :param message: 消息内容
        :param session_list: 目标会话列表（None 表示所有开启此模块的目标）
        :param kwargs: 其他参数（传递给 post_message）
        """
        await Bot.post_message("*", message=message, session_list=session_list, **kwargs)

    @classmethod
    async def fetch_target(
        cls, target_id: str, sender_id: str | None = None, create: bool = False, is_private: bool = False
    ) -> FetchedSessionInfo | None:
        """
        根据场景 ID 获取消息会话信息。

        用于主动获取和向特定目标发送消息。

        :param target_id: 场景 ID
        :param sender_id: 用户 ID（可选）
        :param create: 如果目标不存在是否创建
        :param is_private: 该场景是否为私聊。主动获取的会话没有平台事件可依据，
                           核心也不掌握各平台对私聊前缀的表达，故须由调用方指明，缺省按非私聊处理
        :return: 抓取的会话信息，或 None（获取失败）
        """
        try:
            Logger.trace(f"Fetching target {target_id}")
            # 创建抓取的会话信息
            session = await FetchedSessionInfo.assign(
                target_id=target_id, sender_id=sender_id, fetch=True, create=create, is_private=is_private
            )
        except Exception:
            return None

        return session

    @classmethod
    async def fetch_target_list(cls, target_list: list[str], create: bool = False) -> list[FetchedSessionInfo]:
        """
        批量获取多个目标的会话信息。

        :param target_list: 场景 ID 列表
        :param create: 如果目标不存在是否创建
        :return: 成功获取的会话列表
        """
        fetched = []
        for x in target_list:
            # 如果是字符串，转换为会话对象
            if isinstance(x, str):
                x = await cls.fetch_target(x, create=create)
            # 只添加成功获取的会话
            if isinstance(x, FetchedSessionInfo):
                fetched.append(x)
        return fetched

    @staticmethod
    async def group_sessions_by_channel(
        session_list: list[FetchedSessionInfo],
    ) -> list[list[FetchedSessionInfo]]:
        """
        将待推送的会话按「场景组 + 消息通道」归拢。

        同组同通道的会话对应同一个现实会话（例如一个群内同时存在 OneBot 与 QQ 官方机器人），
        逐个推送会使该会话收到多条重复消息。归拢后每组仅推送一次。

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
            # 查不到通道号即表示该会话没有绑定行，按独立会话处理，不与其它会话归为一组。
            key = (union_id, channel_id) if union_id and channel_id else ("", session_.target_id)
            groups.setdefault(key, []).append(session_)

        return list(groups.values())

    @classmethod
    async def post_message(
        cls,
        module_name: str,
        message: Chainable,
        session_list: list[FetchedSessionInfo] | None = None,
        **kwargs: dict[str, Any],
    ):
        """
        发送消息到开启此模块的指定会话。

        支持向多个会话发送消息，并可根据不同客户端类型发送不同格式的消息。
        同一条消息通道内的会话仅推送一次：先推送队首，队首发送失败时由客户端回调服务端换用下一跳。

        :param module_name: 模块名称（用于权限检查和分析统计，"*" 表示全局）
        :param message: 消息内容，支持字符串或字典
                       如果是字典，键为客户端名称，值为对应的消息内容
                       会使用 "default" 键作为默认消息
        :param session_list: 目标会话列表
                           如果为 None，自动获取开启了该模块的所有目标
        :param kwargs: 其他参数（保留用）
        """
        # 如果未指定会话列表，获取开启了此模块的所有目标
        if session_list is None:
            session_list = await Bot.get_enabled_this_module(module_name)

        # 获取消息队列服务器
        queue_server: "JobQueueServer" = exports["JobQueueServer"]

        # 同一条消息通道仅推送一次，其余会话作为发送失败时的后备
        for hops in await cls.group_sessions_by_channel(session_list):
            # 掉线客户端的任务无人认领，换跳也就无从触发，整条通道将不再有消息送达，因此预先将其剔出跳表
            hops = [hop for hop in hops if Alive.is_alive(hop.client_name)]
            if not hops:
                Logger.warning("Every client of this channel is offline, skipped posting message.")
                continue

            session_ = hops[0]
            session_.next_hops = [hop.target_id for hop in hops[1:]]

            # 将消息转换为该会话支持的消息链格式
            chain = get_message_chain(session_, message)

            # 选择正确格式的消息（根据客户端类型）
            if isinstance(chain, dict):
                # 优先使用客户端特定的消息，否则使用默认消息
                if session_.client_name in chain:
                    post_message = chain[session_.client_name]
                else:
                    post_message = chain["default"]
            else:
                post_message = chain

            # 发送消息
            await queue_server.client_post_message(session_, post_message, module_name)

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

    # 别名定义 - 提供兼容的小驼峰命名方式
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
        queue_server: "JobQueueServer" = exports["JobQueueServer"]
        await queue_server.client_start_typing_signal(session_info)

    @classmethod
    async def end_typing(cls, session_info: SessionInfo) -> None:
        """
        结束“正在输入……”状态。

        :param session_info: 会话信息
        :raises TypeError: 如果 session_info 不是 SessionInfo 类型
        """
        if not isinstance(session_info, SessionInfo):
            raise TypeError("session_info must be a SessionInfo")
        queue_server: "JobQueueServer" = exports["JobQueueServer"]
        await queue_server.client_end_typing_signal(session_info)

    @classmethod
    def register_context_manager(cls, ctx_manager: Any, fetch_session: bool = False) -> int:
        """
        注册一个上下文管理器（通常是某个通讯平台的实现）。

        :param ctx_manager: 上下文管理器实例（应继承 ContextManager）
        :param fetch_session: 是否将此管理器用于抓取会话
        :return: 该管理器在 ContextSlots 中的索引
        """
        # 添加管理器到列表
        cls.ContextSlots.append(ctx_manager)
        # 获取该管理器的索引
        slot_num = len(cls.ContextSlots) - 1

        # 如果标记为抓取会话管理器，保存其索引
        if fetch_session:
            cls.fetched_session_ctx_slot = slot_num

        return slot_num

    @classmethod
    def register_bot(cls, client_name: str = None, private_assets_path: str = None):
        """
        注册机器人实例。

        设置客户端名称和私有资源路径。

        :param client_name: 客户端名称（如 "qq"、"discord" 等）
        :param private_assets_path: 私有资源文件夹路径
                                  如果为 None，自动使用 `assets/private/{client_name}` 路径
        """
        # 设置私有资源路径
        if private_assets_path:
            PrivateAssets.set(private_assets_path)
        else:
            PrivateAssets.set(assets_path / "private" / client_name.lower())

        # 设置系统信息中的客户端名称
        Info.client_name = client_name

    @classmethod
    async def send_direct_message(
        cls,
        target: SessionInfo,
        message: Chainable,
        disable_secret_check: bool = False,
        enable_parse_message: bool = True,
        enable_split_image: bool = True,
    ):
        """
        发送直接消息到场景。

        :param target: 场景会话或场景 ID
        :param message: 消息内容
        :param disable_secret_check: 是否禁用敏感内容检查
        :param enable_parse_message: 是否允许解析消息（平台兼容）
        :param enable_split_image: 是否允许拆分图片（平台兼容）
        """
        # 如果传入的是场景 ID 字符串，先抓取会话
        if isinstance(target, str):
            target = await cls.fetch_target(target)

        # 如果是会话信息，转换为消息会话对象
        if isinstance(target, (SessionInfo, FetchedSessionInfo)):
            target = await FetchedMessageSession.from_session_info(target)

        # 发送消息
        if isinstance(target, (FetchedMessageSession, MessageSession)):
            ...

        if not target:
            raise ValueError("Target not found.")

        # 转换消息格式
        message = get_message_chain(target.session_info, message)

        # 发送直接消息
        await target.send_direct_message(
            message_chain=message,
            disable_secret_check=disable_secret_check,
            enable_parse_message=enable_parse_message,
            enable_split_image=enable_split_image,
        )

    @classmethod
    async def send_private_message(
        cls,
        session_info: SessionInfo,
        message: Chainable,
        user_id: str | None = None,
        enable_parse_message: bool = True,
        enable_split_image: bool = True,
    ) -> list[str]:
        """
        向指定用户单独发送私聊消息。

        消息不会发往 session_info 所指的场景，该会话仅用于确定平台与消息渲染上下文。

        :param session_info: 会话信息
        :param message: 消息内容
        :param user_id: 目标用户 ID（带平台前缀），留空则发给该会话的用户
        :param enable_parse_message: 是否允许解析消息（平台兼容）
        :param enable_split_image: 是否允许拆分图片（平台兼容）
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

        queue_server: "JobQueueServer" = exports["JobQueueServer"]
        message = get_message_chain(session_info, message)

        return_val = await queue_server.client_send_private_message(
            session_info,
            user_id,
            message,
            enable_parse_message=enable_parse_message,
            enable_split_image=enable_split_image,
        )
        return return_val.get("message_id") or []

    @classmethod
    async def get_enabled_this_module(cls, module: str) -> list[FetchedSessionInfo]:
        """
        获取开启了指定模块的所有目标会话列表。

        :param module: 模块名称
        :return: 开启了该模块的会话列表
        """
        # 从数据库获取开启此模块的所有场景 ID（一个 union 下绑定的全部会话都要展开）
        lst = await TargetUnionInfo.get_target_id_list_by_module(module)
        # 退役客户端停止一切主动推送。
        lst = filter_retired_targets(lst)
        fetched = []

        # 逐个抓取这些目标的会话信息
        for target_id in lst:
            x = await cls.fetch_target(target_id)
            if isinstance(x, FetchedSessionInfo):
                fetched.append(x)
        return fetched

    class Hook:
        """
        钩子系统 - 用于在特定事件触发时执行模块代码。
        """

        @staticmethod
        async def trigger(module_or_hook_name: str, session_info: SessionInfo | None = None, args=None) -> Any:
            """
            触发模块钩子或自定义钩子。

            钩子可以在特定事件发生时执行，如 Discord Slash 命令需要 Autocomplete 时。

            :param module_or_hook_name: 模块名称或钩子名称
                                      如果包含 `.`，视为自定义钩子名；否则视为模块名
            :param session_info: 会话信息（可选）
            :param args: 传递给钩子的参数字典
            :return: 钩子函数的返回值
            :raises ValueError: 如果模块或钩子名称无效
            """
            if args is None:
                args = {}

            # 判断是否为自定义钩子（包含 "."）或模块钩子
            hook_mode = False
            if "." in module_or_hook_name:
                hook_mode = True

            # 处理模块钩子
            if not hook_mode:
                if module_or_hook_name:
                    modules = ModulesManager.modules
                    # 检查模块是否存在且已加载
                    if module_or_hook_name in modules:
                        if not modules[module_or_hook_name]._db_load:
                            return None

                        # 执行模块的所有钩子
                        for hook in modules[module_or_hook_name].hooks_list.set:
                            await asyncio.create_task(hook.function(ModuleHookContext(args, session_info=session_info)))
                        return None

                raise ValueError(f"Invalid module name {module_or_hook_name}")

            # 处理自定义钩子
            if module_or_hook_name:
                if module_or_hook_name in ModulesManager.modules_hooks:
                    return await ModulesManager.modules_hooks[module_or_hook_name](
                        ModuleHookContext(args, session_info=session_info)
                    )
            raise ValueError(f"Invalid hook name {module_or_hook_name}")


# 将 Bot 类导出到系统的导出列表中
add_export(Bot)

__all__ = ["Bot"]
