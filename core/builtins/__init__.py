import re
from typing import Union, List

from config import Config
from core.types.message import FetchTarget, FetchedSession as FS, MsgInfo, Session, ModuleHookContext
from core.loader import ModulesManager
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
    FetchedSession = FS

    @staticmethod
    async def sendMessage(target: Union[FS, MessageSession, str], msg: Union[MessageChain, list],
                          disable_secret_check=False,
                          allow_split_image=True):
        if isinstance(target, str):
            target = Bot.FetchTarget.fetch_target(target)
            if not target:
                raise ValueError("Target not found")
        if isinstance(msg, list):
            msg = MessageChain(msg)
        await target.sendDirectMessage(msg, disable_secret_check, allow_split_image)

    @staticmethod
    async def fetch_target(target: str):
        return Bot.FetchTarget.fetch_target(target)

    @staticmethod
    async def get_enabled_this_module(module: str) -> List[FS]:
        lst = BotDBUtil.TargetInfo.get_enabled_this(module)
        fetched = []
        for x in lst:
            x = Bot.FetchTarget.fetch_target(x)
            if isinstance(x, FetchedSession):
                fetched.append(x)
        return fetched

    class Hook:
        @staticmethod
        async def trigger_by_module_name(module_name: str = None, **kwargs):
            if module_name is not None:
                modules = ModulesManager.modules
                if module_name in modules:
                    for hook in modules[module_name].hooks_list.set:
                        await hook.function(Bot.FetchTarget, ModuleHookContext(kwargs))
                    return

            raise ValueError("Invalid module name")

        @staticmethod
        async def trigger_by_hook_name(hook_name: str, **kwargs):
            if hook_name is not None:
                if hook_name in ModulesManager.modules_hooks:
                    await ModulesManager.modules_hooks[hook_name](Bot.FetchTarget, ModuleHookContext(kwargs))
                    return
            raise ValueError("Invalid hook name")


class FetchedSession(FS):
    def __init__(self, targetFrom, targetId, senderFrom=None, senderId=None):
        if senderFrom is None:
            senderFrom = targetFrom
        if senderId is None:
            senderId = targetId
        self.target = MsgInfo(targetId=f'{targetFrom}|{targetId}',
                              senderId=f'{senderFrom}|{senderId}',
                              targetFrom=targetFrom,
                              senderFrom=senderFrom,
                              senderName='',
                              clientName=Bot.client_name,
                              messageId=0,
                              replyId=None)
        self.session = Session(message=False, target=targetId, sender=senderId)
        self.parent = Bot.MessageSession(self.target, self.session)
        if senderId is not None:
            self.parent.target.senderInfo = BotDBUtil.SenderInfo(f'{senderFrom}|{senderId}')


class FetchTarget(FetchTarget):
    match_target_regex = re.compile(r'^(.*)\|(.*)')
    match_sender_regex = re.compile(r'^(.*)\|(.*)')

    @staticmethod
    async def fetch_target(targetId, senderId=None) -> Union[Bot.FetchedSession]:
        matchTarget = re.match(FetchTarget.match_target_regex, targetId)
        if matchTarget:
            targetFrom = senderFrom = matchTarget.group(1)
            targetId = matchTarget.group(2)
            if senderId:
                matchSender = re.match(FetchTarget.match_sender_regex, senderId)
                if matchSender:
                    senderFrom = matchSender.group(1)
                    senderId = matchSender.group(2)
            else:
                senderId = targetId

            return Bot.FetchedSession(targetFrom, targetId, senderFrom, senderId)


Bot.FetchedSession = FetchedSession


base_superuser_list = Config("base_superuser")

if isinstance(base_superuser_list, str):
    base_superuser_list = [base_superuser_list]
