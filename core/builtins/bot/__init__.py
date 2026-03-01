"""
机器人内置模块 - 提供核心的机器人功能接口和会话管理。

该模块定义了 Bot 类，作为系统与各种通讯平台的主要接口，
负责消息处理、会话管理、上下文管理等核心功能。
"""

import asyncio
from typing import Any, TYPE_CHECKING

from core.builtins.message.chain import *
from core.builtins.session.context import ContextManager
from core.builtins.session.info import SessionInfo, FetchedSessionInfo, ModuleHookContext
from core.builtins.session.internal import MessageSession, FetchedMessageSession
from core.builtins.session.lock import ExecutionLockList
from core.builtins.temp import *
from core.config import Config
from core.constants import base_superuser_default
from core.constants.info import Info
from core.constants.path import PrivateAssets, assets_path
from core.database.models import TargetInfo, AnalyticsData
from core.exports import add_export, exports
from core.loader import ModulesManager
from core.logger import Logger

if TYPE_CHECKING:
    from core.queue.client import JobQueueClient
    from core.queue.server import JobQueueServer

enable_analytics = Config("enable_analytics", True)


class Bot:
    """
    机器人核心类。

    提供了机器人的主要功能接口，包括消息处理、会话管理、上下文管理、
    模块钩子执行等。作为系统的中心枢纽，协调各个通讯平台客户端和
    核心业务逻辑的交互。
    """

    # ========== 核心类型引用 ==========
    # 消息会话类型 - 用于处理常规消息
    MessageSession: type[MessageSession] = MessageSession

    # 抓取消息会话类型 - 用于主动获取和发送消息
    FetchedMessageSession: type[FetchedMessageSession] = FetchedMessageSession

    # 模块钩子上下文类型 - 用于模块钩子函数的参数传递
    ModuleHookContext: type[ModuleHookContext] = ModuleHookContext

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
    base_superuser_list = Config("base_superuser", base_superuser_default, cfg_type=(str, list))
    if isinstance(base_superuser_list, str):
        base_superuser_list = [base_superuser_list]

    @classmethod
    async def process_message(cls, session_info: SessionInfo, ctx: Any):
        """
        处理接收到的消息。

        这是消息处理的入口点。将消息会话信息和平台特定的上下文（如对应框架下的消息实例）进行关联，
        然后发送给消息队列处理器进行异步处理。

        :param session_info: 会话信息对象，包含消息、用户、平台等信息
        :param ctx: 平台特定的上下文对象（如 QQ 机器人实例）
        :raises TypeError: 如果 session_info 不是 SessionInfo 类型
        """
        # 验证 session_info 的类型
        if not isinstance(session_info, SessionInfo):
            raise TypeError("session_info must be a SessionInfo")

        # 获取该会话对应的上下文管理器
        ctx_manager = cls.ContextSlots[session_info.ctx_slot]

        # 从上下文管理器获取平台支持的功能特性
        features = ctx_manager.features

        # 将各项功能特性标志设置到会话信息中
        session_info.support_image = features.image
        session_info.support_voice = features.voice
        session_info.support_mention = features.mention
        session_info.support_embed = features.embed
        session_info.support_forward = features.forward
        session_info.support_delete = features.delete
        session_info.support_manage = features.manage
        session_info.support_markdown = features.markdown
        session_info.support_quote = features.quote
        session_info.support_rss = features.rss
        session_info.support_typing = features.typing
        session_info.support_wait = features.wait
        session_info.support_reaction = features.reaction

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
        cls, target_id: str, sender_id: str | None = None, create: bool = False
    ) -> FetchedSessionInfo | None:
        """
        根据目标 ID 获取消息会话信息。

        用于主动获取和向特定目标发送消息。

        :param target_id: 目标 ID（可以是用户、群组等）
        :param sender_id: 发送者 ID（可选）
        :param create: 如果目标不存在是否创建
        :return: 抓取的会话信息，或 None（获取失败）
        """
        try:
            Logger.trace(f"Fetching target {target_id}")
            # 创建抓取的会话信息
            session = await FetchedSessionInfo.assign(
                target_id=target_id, sender_id=sender_id, fetch=True, create=create
            )
        except Exception:
            return None

        return session

    @classmethod
    async def fetch_target_list(cls, target_list: list[str], create: bool = False) -> list[FetchedSessionInfo]:
        """
        批量获取多个目标的会话信息。

        :param target_list: 目标 ID 列表
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

        # 对每个会话发送消息
        for session_ in session_list:
            # 获取消息队列服务器
            queue_server: "JobQueueServer" = exports["JobQueueServer"]

            # 将消息转换为该会话支持的消息链格式
            message = get_message_chain(session_, message)

            # 选择正确格式的消息（根据客户端类型）
            if isinstance(message, dict):
                # 优先使用客户端特定的消息，否则使用默认消息
                if session_.client_name in message:
                    post_message = message[session_.client_name]
                else:
                    post_message = message["default"]
            else:
                post_message = message

            # 发送消息
            await queue_server.client_send_message(session_, post_message)

            # 如果启用分析功能，记录统计数据
            if enable_analytics and module_name:
                await AnalyticsData.create(
                    target_id=session_.target_id,
                    sender_id=session_.sender_id,
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
        发送直接消息到目标。

        :param target: 目标会话或目标 ID
        :param message: 消息内容
        :param disable_secret_check: 是否禁用敏感内容检查
        :param enable_parse_message: 是否允许解析消息（平台兼容）
        :param enable_split_image: 是否允许拆分图片（平台兼容）
        """
        # 如果传入的是目标 ID 字符串，先抓取会话
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
    async def get_enabled_this_module(cls, module: str) -> list[FetchedSessionInfo]:
        """
        获取开启了指定模块的所有目标会话列表。

        :param module: 模块名称
        :return: 开启了该模块的会话列表
        """
        # 从数据库获取开启此模块的所有目标 ID
        lst = await TargetInfo.get_target_list_by_module(module)
        fetched = []

        # 逐个抓取这些目标的会话信息
        for x in lst:
            x = await cls.fetch_target(x.target_id)
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
