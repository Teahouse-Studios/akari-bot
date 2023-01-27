import asyncio
from typing import List

from core.elements import ExecutionLockList, Plain, confirm_command
from core.elements.message import *
from core.elements.message.chain import MessageChain
from core.exceptions import WaitCancelException
from core.utils import MessageTaskManager
from core.utils.i18n import get_target_locale
from database import BotDBUtil


class MessageSession(MessageSession):
    def __init__(self,
                 target: MsgInfo,
                 session: Session):
        self.target = target
        self.session = session
        self.sent: List[MessageChain] = []
        self.prefixes: List[str] = []
        self.data = BotDBUtil.TargetInfo(self.target.targetId)
        self.muted = self.data.is_muted
        self.options = self.data.options
        self.custom_admins = self.data.custom_admins
        self.enabled_modules = self.data.enabled_modules
        self.locale = self.data.locale

    async def waitConfirm(self, msgchain=None, quote=True, delete=True) -> bool:
        send = None
        ExecutionLockList.remove(self)
        if msgchain is not None:
            msgchain = MessageChain(msgchain)
            msgchain.append(Plain('（发送“是”或符合确认条件的词语来确认）'))
            send = await self.sendMessage(msgchain, quote)
        flag = asyncio.Event()
        MessageTaskManager.add_task(self, flag)
        await flag.wait()
        result = MessageTaskManager.get_result(self)
        if result:
            if msgchain is not None and delete:
                await send.delete()
            if result.asDisplay() in confirm_command:
                return True
            return False
        else:
            raise WaitCancelException

    async def waitNextMessage(self, msgchain=None, quote=True, delete=False) -> MessageSession:
        sent = None
        ExecutionLockList.remove(self)
        if msgchain is not None:
            msgchain = MessageChain(msgchain)
            msgchain.append(Plain('（发送符合条件的词语来确认）'))
            sent = await self.sendMessage(msgchain, quote)
        flag = asyncio.Event()
        MessageTaskManager.add_task(self, flag)
        await flag.wait()
        result = MessageTaskManager.get_result(self)
        if delete and sent is not None:
            await sent.delete()
        if result:
            return result
        else:
            raise WaitCancelException

    async def waitReply(self, msgchain, quote=True) -> MessageSession:
        ExecutionLockList.remove(self)
        msgchain = MessageChain(msgchain)
        msgchain.append(Plain('（请使用指定的词语回复本条消息）'))
        send = await self.sendMessage(msgchain, quote)
        flag = asyncio.Event()
        MessageTaskManager.add_task(self, flag, reply=send.messageId)
        await flag.wait()
        result = MessageTaskManager.get_result(self)
        if result:
            return result
        else:
            raise WaitCancelException

    async def waitAnyone(self, msgchain=None, delete=False) -> MessageSession:
        send = None
        ExecutionLockList.remove(self)
        if msgchain is not None:
            msgchain = MessageChain(msgchain)
            send = await self.sendMessage(msgchain, quote=False)
        flag = asyncio.Event()
        MessageTaskManager.add_task(self, flag, all_=True)
        await flag.wait()
        result = MessageTaskManager.get()[self.target.targetId]['all']
        if 'result' in result:
            if send is not None and delete:
                await send.delete()
            return MessageTaskManager.get()[self.target.targetId]['all']['result']
        else:
            raise WaitCancelException

    async def sleep(self, s):
        ExecutionLockList.remove(self)
        await asyncio.sleep(s)

    def checkSuperUser(self):
        return True if self.target.senderInfo.query.isSuperUser else False

    def t(self, *args, **kwargs) -> str:
        return get_target_locale(self).t(*args, **kwargs)


__all__ = ["MessageSession"]
