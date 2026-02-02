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
    MessageSession: type[MessageSession] = MessageSession
    FetchedMessageSession: type[FetchedMessageSession] = FetchedMessageSession
    ModuleHookContext: type[ModuleHookContext] = ModuleHookContext
    ExecutionLockList = ExecutionLockList
    Info = Info
    Temp = Temp
    PrivateAssets = PrivateAssets
    ContextSlots: list[ContextManager] = []
    fetched_session_ctx_slot = 0

    base_superuser_list = Config(
        "base_superuser", base_superuser_default, cfg_type=(str, list)
    )
    if isinstance(base_superuser_list, str):
        base_superuser_list = [base_superuser_list]

    @classmethod
    async def process_message(cls, session_info: SessionInfo, ctx: Any):
        """
        :param session_info: SessionInfo
        :param ctx: Context
        :return: None
        """
        if not isinstance(session_info, SessionInfo):
            raise TypeError("session_info must be a SessionInfo")
        ctx_manager = cls.ContextSlots[session_info.ctx_slot]
        features = ctx_manager.features
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
            ctx_manager.add_context(session_info, ctx)
            queue_client: "JobQueueClient" = exports["JobQueueClient"]
            await queue_client.send_message_to_server(session_info)
            await asyncio.sleep(1)  # 清理上下文时等待1秒，删的太快了会报错
            ctx_manager.del_context(session_info)

        asyncio.create_task(_process_msg())

    @staticmethod
    async def post_global_message(
        message: Chainable,
        session_list: list[FetchedSessionInfo] | None = None,
        **kwargs: dict[str, Any],
    ):
        await Bot.post_message(
            "*", message=message, session_list=session_list, **kwargs
        )

    @classmethod
    async def fetch_target(cls,
                           target_id: str,
                           sender_id: str | None = None,
                           create: bool = False
                           ) -> FetchedSessionInfo | None:
        """
        尝试从数据库记录的对象ID中取得对象消息会话，实际此会话中的消息文本会被设为False（因为本来就没有）。
        """
        try:
            Logger.trace(f"Fetching target {target_id}")
            session = await FetchedSessionInfo.assign(target_id=target_id,
                                                      sender_id=sender_id,
                                                      fetch=True,
                                                      create=create)
        except Exception:
            return None

        return session

    @classmethod
    async def fetch_target_list(cls,
                                target_list: list[str],
                                create: bool = False
                                ) -> list[FetchedSessionInfo]:
        """
        尝试从数据库记录的对象ID中取得对象消息会话，实际此会话中的消息文本会被设为False（因为本来就没有）。
        """
        fetched = []
        for x in target_list:
            if isinstance(x, str):
                x = await cls.fetch_target(x, create=create)
            if isinstance(x, FetchedSessionInfo):
                fetched.append(x)
        return fetched

    @classmethod
    async def post_message(cls,
                           module_name: str,
                           message: Chainable,
                           session_list: list[FetchedSessionInfo] | None = None,
                           **kwargs: dict[str, Any],
                           ):
        """
        尝试向开启此模块的对象发送一条消息。

        :param module_name: 模块名称。
        :param message: 消息文本，若传入dict则会根据键名针对不同的客户端发送不同格式的消息（默认键名为default）。
        :param session_list: 用户列表。
        """
        if session_list is None:
            session_list = await Bot.get_enabled_this_module(module_name)
        for session_ in session_list:
            queue_server: "JobQueueServer" = exports["JobQueueServer"]
            message = get_message_chain(session_, message)
            if isinstance(message, dict):
                if session_.client_name in message:
                    post_message = message[session_.client_name]
                else:
                    post_message = message["default"]
            else:
                post_message = message
            await queue_server.client_send_message(session_, post_message)
            if enable_analytics and module_name:
                await AnalyticsData.create(target_id=session_.target_id,
                                           sender_id=session_.sender_id,
                                           command="",
                                           module_name=module_name,
                                           module_type="schedule")

    postMessage = post_message
    postGlobalMessage = post_global_message

    @classmethod
    async def start_typing(cls, session_info: SessionInfo) -> None:
        """
        :param session_info: SessionInfo
        """
        if not isinstance(session_info, SessionInfo):
            raise TypeError("session_info must be a SessionInfo")
        queue_server: "JobQueueServer" = exports["JobQueueServer"]
        await queue_server.client_start_typing_signal(session_info)

    @classmethod
    async def end_typing(cls, session_info: SessionInfo) -> None:
        if not isinstance(session_info, SessionInfo):
            raise TypeError("session_info must be a SessionInfo")
        queue_server: "JobQueueServer" = exports["JobQueueServer"]
        await queue_server.client_end_typing_signal(session_info)

    @classmethod
    def register_context_manager(cls, ctx_manager: Any, fetch_session: bool = False) -> int:
        """
        :param ctx_manager: ContextManager
        :param fetch_session: If True, fetched session will be used
        :return: Index of the ContextManager in ContextSlots
        """
        cls.ContextSlots.append(ctx_manager)
        slot_num = len(cls.ContextSlots) - 1
        if fetch_session:
            cls.fetched_session_ctx_slot = slot_num

        return slot_num

    @classmethod
    def register_bot(cls, client_name: str = None,
                     private_assets_path: str = None):
        """
        :param client_name: Client name
        :param private_assets_path: Private assets path
        :return: None
        """
        if private_assets_path:
            PrivateAssets.set(private_assets_path)
        else:
            PrivateAssets.set(assets_path / "private" / client_name.lower())
        Info.client_name = client_name

    @classmethod
    async def send_direct_message(cls,
                                  target: SessionInfo,
                                  message: Chainable,
                                  disable_secret_check: bool = False,
                                  enable_parse_message: bool = True,
                                  enable_split_image: bool = True,
                                  ):
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
            enable_parse_message=enable_parse_message,
            enable_split_image=enable_split_image,
        )

    @classmethod
    async def get_enabled_this_module(cls, module: str) -> list[FetchedSessionInfo]:
        lst = await TargetInfo.get_target_list_by_module(module)
        fetched = []
        for x in lst:
            x = await cls.fetch_target(x.target_id)
            if isinstance(x, FetchedSessionInfo):
                fetched.append(x)
        return fetched

    class Hook:
        @staticmethod
        async def trigger(module_or_hook_name: str, session_info: SessionInfo | None = None, args=None) -> Any:
            if args is None:
                args = {}
            hook_mode = False
            if "." in module_or_hook_name:
                hook_mode = True
            if not hook_mode:
                if module_or_hook_name:
                    modules = ModulesManager.modules
                    if module_or_hook_name in modules:
                        if not modules[module_or_hook_name]._db_load:
                            return None

                        for hook in modules[module_or_hook_name].hooks_list.set:
                            await asyncio.create_task(
                                hook.function(ModuleHookContext(args, session_info=session_info))
                            )
                        return None

                raise ValueError(f"Invalid module name {module_or_hook_name}")
            if module_or_hook_name:
                if module_or_hook_name in ModulesManager.modules_hooks:
                    return await ModulesManager.modules_hooks[module_or_hook_name](
                        ModuleHookContext(args, session_info=session_info)
                    )
            raise ValueError(f"Invalid hook name {module_or_hook_name}")


add_export(Bot)

__all__ = ["Bot"]
