from typing import Union, List

from config import Config
from core.types.message import FetchTarget, FetchedSession
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

    @staticmethod
    async def sendMessage(target: Union[FetchedSession, MessageSession, str], msg: Union[MessageChain, list],
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
    async def get_enabled_this_module(module: str) -> List[FetchedSession]:
        lst = BotDBUtil.TargetInfo.get_enabled_this(module)
        fetched = []
        for x in lst:
            x = Bot.FetchTarget.fetch_target(x)
            if isinstance(x, FetchedSession):
                fetched.append(x)
        return fetched


base_superuser_list = Config("base_superuser")

if isinstance(base_superuser_list, str):
    base_superuser_list = [base_superuser_list]
