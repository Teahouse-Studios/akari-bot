import asyncio

from core.elements import ExecutionLockList, Plain, confirm_command
from core.elements.message import *
from core.elements.message.chain import MessageChain
from core.utils import MessageTaskManager


class MessageSession(MessageSession):
    async def waitConfirm(self, msgchain=None, quote=True, delete=True):
        send = None
        ExecutionLockList.remove(self)
        if msgchain is not None:
            msgchain = MessageChain(msgchain)
            msgchain.append(Plain('（发送“是”或符合确认条件的词语来确认）'))
            send = await self.sendMessage(msgchain, quote)
        flag = asyncio.Event()
        MessageTaskManager.add_task(self, flag)
        await flag.wait()
        if msgchain is not None and delete:
            await send.delete()
        if MessageTaskManager.get_result(self).asDisplay() in confirm_command:
            return True
        return False

    async def waitAnyone(self, msgchain=None, delete=False):
        send = None
        ExecutionLockList.remove(self)
        if msgchain is not None:
            msgchain = MessageChain(msgchain)
            send = await self.sendMessage(msgchain, quote=False)
        flag = asyncio.Event()
        MessageTaskManager.add_task(self, flag, all_=True)
        await flag.wait()
        if send is not None and delete:
            await send.delete()
        return MessageTaskManager.get()[self.target.targetId]['all']['result']


__all__ = ["MessageSession"]
