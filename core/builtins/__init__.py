import asyncio
from typing import Union, List

from config import Config
from core.loader import ModulesManager
from core.types.message import FetchTarget, FetchedSession as FetchedSessionT, MsgInfo, Session, ModuleHookContext
from database import BotDBUtil
from .message import *
from .message.chain import *
from .message.internal import *
from .tasks import *
from .temp import *
from .utils import *


class Bot:
    MessageSession = MessageSession
    FetchTarget = FetchTarget
    client_name = FetchTarget.name
    FetchedSession = FetchedSessionT
    ModuleHookContext = ModuleHookContext
    ExecutionLockList = ExecutionLockList

    @staticmethod
    async def send_message(target: Union[FetchedSessionT, MessageSession, str], msg: Union[MessageChain, list],
                           disable_secret_check=False,
                           allow_split_image=True):
        if isinstance(target, str):
            target = Bot.FetchTarget.fetch_target(target)
            if not target:
                raise ValueError("Target not found")
        if isinstance(msg, list):
            msg = MessageChain(msg)
        await target.send_direct_message(msg, disable_secret_check, allow_split_image)

    @staticmethod
    async def fetch_target(target: str):
        return Bot.FetchTarget.fetch_target(target)

    @staticmethod
    async def get_enabled_this_module(module: str) -> List[FetchedSessionT]:
        lst = BotDBUtil.TargetInfo.get_enabled_this(module)
        fetched = []
        for x in lst:
            x = Bot.FetchTarget.fetch_target(x)
            if isinstance(x, FetchedSession):
                fetched.append(x)
        return fetched

    class Hook:
        @staticmethod
        async def trigger(module_or_hook_name: str, args):
            hook_mode = False
            if '.' in module_or_hook_name:
                hook_mode = True
            if not hook_mode:
                if module_or_hook_name is not None:
                    modules = ModulesManager.modules
                    if module_or_hook_name in modules:
                        for hook in modules[module_or_hook_name].hooks_list.set:
                            await asyncio.create_task(hook.function(Bot.FetchTarget, ModuleHookContext(args)))
                        return

                raise ValueError("Invalid module name")
            else:
                if module_or_hook_name is not None:
                    if module_or_hook_name in ModulesManager.modules_hooks:
                        await asyncio.create_task(ModulesManager.modules_hooks[module_or_hook_name](Bot.FetchTarget,
                                                                                                    ModuleHookContext(
                                                                                                        args)))
                        return
                raise ValueError("Invalid hook name")


class FetchedSession(FetchedSessionT):
    def __init__(self, target_from, target_id, sender_from=None, sender_id=None):
        if sender_from is None:
            sender_from = target_from
        if sender_id is None:
            sender_id = target_id
        self.target = MsgInfo(target_id=f'{target_from}|{target_id}',
                              sender_id=f'{sender_from}|{sender_id}',
                              target_from=target_from,
                              sender_from=sender_from,
                              sender_name='',
                              client_name=Bot.client_name,
                              message_id=0,
                              reply_id=None)
        self.session = Session(message=False, target=target_id, sender=sender_id)
        self.parent = Bot.MessageSession(self.target, self.session)
        if sender_id is not None:
            self.parent.target.sender_info = BotDBUtil.SenderInfo(f'{sender_from}|{sender_id}')


Bot.FetchedSession = FetchedSession

base_superuser_list = Config("base_superuser")

if isinstance(base_superuser_list, str):
    base_superuser_list = [base_superuser_list]
