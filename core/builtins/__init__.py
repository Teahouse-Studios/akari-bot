import asyncio
from typing import Any, Dict, List, Optional, Union

from core.config import Config
from core.constants.default import base_superuser_default
from core.constants.info import Info, Secret
from core.constants.path import PrivateAssets
from core.database.models import AnalyticsData, TargetInfo
from core.exports import add_export
from core.loader import ModulesManager
from core.logger import Logger
from core.types.message import MsgInfo, Session, ModuleHookContext
from .message import *
from .message.chain import *
from .message.elements import MessageElement
from .message.internal import *
from .temp import *
from .utils import *

enable_analytics = Config("enable_analytics", False)


class Bot:
    MessageSession = MessageSession
    FetchTarget = FetchTarget
    client_name = FetchTarget.name
    ExecutionLockList = ExecutionLockList
    FetchedSession = FetchedSession
    ModuleHookContext = ModuleHookContext
    PrivateAssets = PrivateAssets
    Info = Info
    Secret = Secret
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
        sender_from: Optional[str],
        sender_id: Optional[Union[str, int]],
    ):
        target_id_ = f"{target_from}|{target_id}"
        sender_id_ = None
        if sender_from and sender_id:
            sender_id_ = f"{sender_from}|{sender_id}"
        self.target = MsgInfo(
            target_id=target_id_,
            sender_id=sender_id_,
            target_from=target_from,
            sender_from=sender_from,
            sender_name="",
            client_name=Bot.Info.client_name,
            message_id=0,
        )
        self.session = Session(message=False, target=target_id, sender=sender_id)
        self.parent = Bot.MessageSession(self.target, self.session)


Bot.FetchedSession = FetchedSession


class FetchTarget(FetchTarget):
    @staticmethod
    async def fetch_target_list(target_list: list) -> List[FetchedSession]:
        lst = []
        for x in target_list:
            fet = await Bot.FetchTarget.fetch_target(x)
            if fet:
                lst.append(fet)
        return lst

    @staticmethod
    async def post_message(
        module_name: str,
        message: Union[str, list, dict, MessageChain, MessageElement],
        target_list: Optional[List[FetchedSession]] = None,
        i18n: bool = False,
        **kwargs: Dict[str, Any],
    ):
        module_ = None if module_name == "*" else module_name
        if target_list:
            for x in target_list:
                try:
                    if isinstance(message, dict) and i18n:  # 提取字典语言映射
                        message = message.get(x.parent.locale, message.get("fallback", ""))

                    msgchain = message
                    if isinstance(message, str):
                        if i18n:
                            msgchain = MessageChain(I18NContext(message, **kwargs))
                        else:
                            msgchain = MessageChain(Plain(message))
                    msgchain = MessageChain(msgchain)
                    await x.send_direct_message(msgchain)
                    if enable_analytics and module_:
                        await AnalyticsData.create(target_id=x.target.target_id,
                                                   sender_id=x.target.sender_id,
                                                   command="",
                                                   module_name=module_,
                                                   module_type="schedule")
                except Exception:
                    Logger.exception()
        else:
            get_target_id = await TargetInfo.get_target_list_by_module(
                module_, Bot.Info.client_name
            )
            for x in get_target_id:
                fetch = await Bot.FetchTarget.fetch_target(x.target_id)
                if fetch:
                    if x.muted:
                        continue
                    try:
                        if isinstance(message, dict) and i18n:  # 提取字典语言映射
                            message = message.get(fetch.parent.locale, message.get("fallback", ""))

                        msgchain = message
                        if isinstance(message, str):
                            if i18n:
                                msgchain = MessageChain(I18NContext(message, **kwargs))
                            else:
                                msgchain = MessageChain(Plain(message))
                        msgchain = MessageChain(msgchain)
                        await fetch.send_direct_message(msgchain)
                        if enable_analytics and module_:
                            await AnalyticsData.create(target_id=fetch.target.target_id,
                                                       sender_id=fetch.target.sender_id,
                                                       command="",
                                                       module_name=module_,
                                                       module_type="schedule")
                    except Exception:
                        Logger.exception()

    @staticmethod
    async def post_global_message(
        message: str,
        target_list: Optional[List[FetchedSession]] = None,
        i18n: bool = False,
        **kwargs: Dict[str, Any]
    ):
        await Bot.FetchTarget.post_message(
            "*", message=message, target_list=target_list, i18n=i18n, **kwargs
        )


Bot.FetchTarget = FetchTarget

base_superuser_list = Config(
    "base_superuser", base_superuser_default, cfg_type=(str, list)
)

if isinstance(base_superuser_list, str):
    base_superuser_list = [base_superuser_list]


add_export(Bot)
