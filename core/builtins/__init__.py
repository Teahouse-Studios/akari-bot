import asyncio
from typing import Any, Dict, List, Optional, Union

from core.config import Config
from core.constants.info import Info
from core.exports import add_export
from core.loader import ModulesManager
from core.types.message import MsgInfo, Session, ModuleHookContext
from .message import *
from .message.chain import *
from .message.internal import *
from .temp import *
from .utils import *
from ..constants import base_superuser_default
from ..database.models import TargetInfo
from ..logger import Logger


class Bot:
    MessageSession = MessageSession
    FetchTarget = FetchTarget
    client_name = FetchTarget.name
    FetchedSession = FetchedSession
    ModuleHookContext = ModuleHookContext
    ExecutionLockList = ExecutionLockList
    Info = Info
    Temp = Temp

    @staticmethod
    async def send_message(
        target: Union[FetchedSession, MessageSession, str],
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
        sender_from: Optional[str] = None,
        sender_id: Optional[Union[int, str]] = None,
    ):
        if not sender_from:
            sender_from = target_from
        if not sender_id:
            sender_id = target_id
        self.target = MsgInfo(
            target_id=f"{target_from}|{target_id}",
            sender_id=f"{sender_from}|{sender_id}",
            target_from=target_from,
            sender_from=sender_from,
            sender_name="",
            client_name=Bot.client_name,
            message_id=0,
        )
        self.session = Session(message=False, target=target_id, sender=sender_id)
        self.parent = Bot.MessageSession(self.target, self.session)

#        if sender_id:
#            self.parent.target.sender_id = exports.get("BotDBUtil").SenderInfo(
#                f"{sender_from}|{sender_id}"
#            )


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

base_superuser_list = Config(
    "base_superuser", base_superuser_default, cfg_type=(str, list)
)

if isinstance(base_superuser_list, str):
    base_superuser_list = [base_superuser_list]


add_export(Bot)
