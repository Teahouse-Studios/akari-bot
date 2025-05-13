import asyncio
from typing import Any, Dict, List, Optional, Union, Sequence

from attrs import define

from core.config import Config
from core.constants.info import Info
from core.exports import add_export, exports
from core.loader import ModulesManager
from core.types.message import ModuleHookContext
from .message import *
from .message.chain import *
from .message.internal import *
from .session import SessionInfo
from .temp import *
from .utils import *
from ..constants import base_superuser_default
from ..database.models import TargetInfo
from ..logger import Logger

from core.builtins.session import MessageSession, FetchedSession, FetchTarget
from core.builtins.session.context import ContextManager
from core.builtins.session.lock import ExecutionLockList

from core.builtins.session.features import Features


class Bot:
    MessageSession = MessageSession
    FetchTarget = FetchTarget
    client_name = ''
    FetchedSession = FetchedSession
    ModuleHookContext = ModuleHookContext
    ExecutionLockList = ExecutionLockList
    Info = Info
    Temp = Temp
    base_superuser_list = Config(
        "base_superuser", base_superuser_default, cfg_type=(str, list)
    )
    ContextSlots: list[ContextManager] = []

    if isinstance(base_superuser_list, str):
        base_superuser_list = [base_superuser_list]

    @classmethod
    async def process_message(cls, session_info: SessionInfo, ctx: Any):
        """
        处理消息
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

        await ctx_manager.add_context(session_info, ctx)
        async with ctx_manager.Typing(session_info) as typing:
            await exports['JobQueueClient'].send_message_to_server(session_info)
        await ctx_manager.del_context(session_info)

    @classmethod
    def register_context_manager(cls, ctx_manager: Any) -> int:
        """
        :param ctx: ContextManager
        :return: Index of the ContextManager in ContextSlots
        """
        cls.ContextSlots.append(ctx_manager)
        return len(cls.ContextSlots) - 1

    @staticmethod
    async def send_direct_message(
        target: SessionInfo,
        msg: Union[MessageChain, list],
        disable_secret_check: bool = False,
        enable_parse_message: bool = True,
        enable_split_image: bool = True,
    ):
        if isinstance(target, str):
            target = await Bot.FetchTarget.fetch_target(target)
        if isinstance(msg, list):
            msg = MessageChain(msg)
        Logger.info(target.__dict__)
        await target.send_direct_message(
            message_chain=msg,
            disable_secret_check=disable_secret_check,
            enable_parse_message=enable_parse_message,
            enable_split_image=enable_split_image,
        )

    @staticmethod
    async def fetch_target(target: str):
        return Bot.FetchTarget.fetch_target(target)

    @staticmethod
    async def get_enabled_this_module(module: str) -> List[FetchedSession]:
        lst = await TargetInfo.get_target_list_by_module(module)
        fetched = []
        for x in lst:
            x = Bot.FetchTarget.fetch_target(x.target_id)
            if isinstance(x, FetchedSession):
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
                                hook.function(Bot.FetchTarget, ModuleHookContext(args))
                            )
                        return

                raise ValueError(f"Invalid module name {module_or_hook_name}")
            if module_or_hook_name:
                if module_or_hook_name in ModulesManager.modules_hooks:
                    await asyncio.create_task(
                        ModulesManager.modules_hooks[module_or_hook_name](
                            Bot.FetchTarget, ModuleHookContext(args)
                        )
                    )
                    return
            raise ValueError(f"Invalid hook name {module_or_hook_name}")


class FetchedSession(FetchedSession):
    def __init__(
        self,
        target_from: str,
        target_id: Union[int, str],
        sender_from: Optional[str],
        sender_id: Optional[Union[str, int]],
    ):
        target_id_ = f"{target_from}|{target_id}"
        sender_id_ = None
        if sender_from and sender_id:
            sender_id_ = f"{sender_from}|{sender_id}"
        self.session_info = SessionInfo(
            target_id=target_id_,
            sender_id=sender_id_,
            target_from=target_from,
            sender_from=sender_from,
            sender_name="",
            client_name=Bot.client_name,
            message_id=0,
        )


Bot.FetchedSession = FetchedSession


class FetchTarget(FetchTarget):
    @staticmethod
    async def post_global_message(
        message: str,
        user_list: Optional[List[FetchedSession]] = None,
        i18n: bool = False,
        **kwargs: Dict[str, Any],
    ):
        await Bot.FetchTarget.post_message(
            "*", message=message, user_list=user_list, i18n=i18n, **kwargs
        )


Bot.FetchTarget = FetchTarget

add_export(Bot)


__all__ = [
    "Bot",
    "FetchedSession",
    "FetchTarget"]
