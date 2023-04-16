from typing import Union

from core.types.message import FetchTarget, FetchedSession
from .message import *
from .message.chain import *
from .message.internal import *
from .tasks import *
from .temp import *
from .utils import *



class Bot:
    MessageSession = MessageSession
    FetchTarget = FetchTarget

    async def sendMessage(self, target: Union[FetchedSession, str], msg: Union[MessageChain, list],
                          disable_secret_check=False,
                          allow_split_image=True):
        if isinstance(target, str):
            target = FetchTarget.fetch_target(target)
        if isinstance(msg, list):
            msg = MessageChain(msg)
        await target.sendDirectMessage(msg, disable_secret_check, allow_split_image)
