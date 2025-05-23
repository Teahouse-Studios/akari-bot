import asyncio
from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING

from core.config import Config
from core.constants.info import Info
from core.exports import add_export, exports
from core.loader import ModulesManager
from core.types.message import ModuleHookContext
from .message import *
from .message.chain import *
from .message.internal import *
from .session import SessionInfo, FetchedSessionInfo
from .temp import *
from .utils import *
from .utils import determine_target_from, determine_sender_from
from ..constants import base_superuser_default
from ..database.models import TargetInfo
from ..logger import Logger

from core.builtins.session import MessageSession
from core.builtins.session.context import ContextManager
from core.builtins.session.lock import ExecutionLockList

from core.builtins.session.features import Features

if TYPE_CHECKING:
    from ..queue.client import JobQueueClient
    from ..queue.server import JobQueueServer


class Bot:
    MessageSession = MessageSession
    ModuleHookContext = ModuleHookContext
    ExecutionLockList = ExecutionLockList
    Info = Info
    Temp = Temp
    PrivateAssets = PrivateAssets
    ContextSlots: list[ContextManager] = []

    client_name = ''
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
        session_info.support_markdown = features.markdown
        session_info.support_quote = features.quote
        session_info.support_rss = features.rss
        session_info.support_typing = features.typing
        session_info.support_wait = features.wait

        async def _process_msg():
            await ctx_manager.add_context(session_info, ctx)
            queue_client: "JobQueueClient" = exports["JobQueueClient"]
            await queue_client.send_message_signal_to_server(session_info)
            await ctx_manager.del_context(session_info)

        asyncio.create_task(_process_msg())

    @staticmethod
    async def post_global_message(
        message: str,
        session_list: Optional[List[FetchedSessionInfo]] = None,
        i18n: bool = False,
        **kwargs: Dict[str, Any],
    ):
        await Bot.post_message(
            "*", message=message, session_list=session_list, **kwargs
        )
        ...

    @classmethod
    async def fetch_target(cls,
                           target_id: str, sender_id: Optional[Union[int, str]] = None
                           ) -> FetchedSessionInfo:
        """
        尝试从数据库记录的对象ID中取得对象消息会话，实际此会话中的消息文本会被设为False（因为本来就没有）。
        """
        # todo
        session = await FetchedSessionInfo.assign(target_id=target_id,
                                                  sender_id=sender_id,
                                                  client_name=Bot.client_name,
                                                  ctx_slot=cls.fetched_session_ctx_slot, create=False)
        return session

    @classmethod
    async def fetch_target_list(cls,
                                target_list: List[Union[int, str]]
                                ) -> List[FetchedSessionInfo]:
        """
        尝试从数据库记录的对象ID中取得对象消息会话，实际此会话中的消息文本会被设为False（因为本来就没有）。
        """
        fetched = []
        for x in target_list:
            if isinstance(x, str):
                x = await cls.fetch_target(x)
            if isinstance(x, FetchedSessionInfo):
                fetched.append(x)
        return fetched

    @classmethod
    async def post_message(cls,
                           module_name: str,
                           message: Union[str, MessageChain],
                           session_list: Optional[List[FetchedSessionInfo]] = None,
                           **kwargs: Dict[str, Any],
                           ):
        """
        尝试向开启此模块的对象发送一条消息。

        :param module_name: 模块名称。
        :param message: 消息文本。
        :param session_list: 用户列表。
        """
        if session_list is None:
            session_list = await Bot.get_enabled_this_module(module_name)
        if isinstance(message, str):
            message = MessageChain.assign(message)
        for session in session_list:
            queue_server: "JobQueueServer" = exports["JobQueueServer"]
            await queue_server.send_message_signal_to_client(session, message)

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
        await queue_server.start_typing_signal_to_client(session_info)

    @classmethod
    async def end_typing(cls, session_info: SessionInfo) -> None:
        if not isinstance(session_info, SessionInfo):
            raise TypeError("session_info must be a SessionInfo")
        queue_server: "JobQueueServer" = exports["JobQueueServer"]
        await queue_server.end_typing_signal_to_client(session_info)

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
                     private_assets_path: str = None,
                     dirty_word_check=False,
                     use_url_manager=False,
                     use_url_md_format=False):
        """
        :param client_name: Client name
        :param private_assets_path: Private assets path
        :param dirty_word_check: Whether to check for dirty words
        :param use_url_manager: Whether to use URL manager
        :param use_url_md_format: Whether to use URL markdown format
        :return: None
        """
        cls.client_name = client_name
        if private_assets_path:
            cls.PrivateAssets = PrivateAssets.set(private_assets_path)
        Info.dirty_word_check = dirty_word_check
        Info.client_name = client_name
        Info.use_url_manager = use_url_manager
        Info.use_url_md_format = use_url_md_format

    @classmethod
    async def send_direct_message(cls,
                                  target: SessionInfo,
                                  msg: Union[MessageChain, list],
                                  disable_secret_check: bool = False,
                                  enable_parse_message: bool = True,
                                  enable_split_image: bool = True,
                                  ):
        if isinstance(target, str):
            target = await cls.fetch_target(target)
        if isinstance(msg, list):
            msg = MessageChain(msg)
        Logger.info(target.__dict__)
        m = await Bot.MessageSession.from_session_info(session=target)
        await m.send_direct_message(
            message_chain=msg,
            disable_secret_check=disable_secret_check,
            enable_parse_message=enable_parse_message,
            enable_split_image=enable_split_image,
        )

    @classmethod
    async def get_enabled_this_module(cls, module: str) -> List[FetchedSessionInfo]:
        lst = await TargetInfo.get_target_list_by_module(module)
        fetched = []
        for x in lst:
            x = cls.fetch_target(x.target_id)
            if isinstance(x, FetchedSessionInfo):
                fetched.append(x)
        return fetched

    class Hook:
        @staticmethod
        async def trigger(module_or_hook_name: str, args):
            hook_mode = False
            if "." in module_or_hook_name:
                hook_mode = True
            if not hook_mode:
                if module_or_hook_name:
                    modules = ModulesManager.modules
                    if module_or_hook_name in modules:
                        for hook in modules[module_or_hook_name].hooks_list.set:
                            await asyncio.create_task(
                                hook.function(Bot, ModuleHookContext(args))
                            )
                        return

                raise ValueError(f"Invalid module name {module_or_hook_name}")
            if module_or_hook_name:
                if module_or_hook_name in ModulesManager.modules_hooks:
                    await asyncio.create_task(
                        ModulesManager.modules_hooks[module_or_hook_name](
                            Bot, ModuleHookContext(args)
                        )
                    )
                    return
            raise ValueError(f"Invalid hook name {module_or_hook_name}")


add_export(Bot)


__all__ = ["Bot"]
