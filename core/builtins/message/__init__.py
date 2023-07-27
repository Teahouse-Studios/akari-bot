import asyncio
from datetime import datetime
from typing import List

from core.builtins.message.chain import *
from core.builtins.message.internal import *
from core.builtins.tasks import MessageTaskManager
from core.builtins.temp import ExecutionLockList
from core.builtins.utils import confirm_command
from core.exceptions import WaitCancelException
from core.types.message import *
from core.utils.i18n import Locale
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
        self.locale = Locale(self.data.locale)
        self.timestamp = datetime.now()

    async def waitConfirm(self, msgchain=None, quote=True, delete=True) -> bool:
        send = None
        ExecutionLockList.remove(self)
        if msgchain is not None:
            msgchain = MessageChain(msgchain)
            msgchain.append(Plain(self.locale.t("message.wait.confirm.prompt.type1")))
            send = await self.sendMessage(msgchain, quote)
        flag = asyncio.Event()
        MessageTaskManager.add_task(self, flag)
        await flag.wait()
        result = MessageTaskManager.get_result(self)
        if result is not None:
            if msgchain is not None and delete:
                await send.delete()
            if result.asDisplay(text_only=True) in confirm_command:
                return True
            return False
        else:
            raise WaitCancelException

    async def waitNextMessage(self, msgchain=None, quote=True, delete=False, append_instruction=True) -> MessageSession:
        sent = None
        ExecutionLockList.remove(self)
        if msgchain is not None:
            msgchain = MessageChain(msgchain)
            if append_instruction:
                msgchain.append(Plain(self.locale.t("message.wait.confirm.prompt.type2")))
            sent = await self.sendMessage(msgchain, quote)
        flag = asyncio.Event()
        MessageTaskManager.add_task(self, flag)
        await flag.wait()
        result = MessageTaskManager.get_result(self)
        if delete and sent is not None:
            await sent.delete()
        if result is not None:
            return result
        else:
            raise WaitCancelException

    async def waitReply(self, msgchain, quote=True, all_=False, append_instruction=True) -> MessageSession:
        ExecutionLockList.remove(self)
        msgchain = MessageChain(msgchain)
        if append_instruction:
            msgchain.append(Plain(self.locale.t("message.reply.prompt")))
        send = await self.sendMessage(msgchain, quote)
        flag = asyncio.Event()
        MessageTaskManager.add_task(self, flag, reply=send.messageId, all_=all_)
        await flag.wait()
        result = MessageTaskManager.get_result(self)
        if result is not None:
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
        result = MessageTaskManager.get()[self.target.targetId]['all'][self]
        if 'result' in result:
            if send is not None and delete:
                await send.delete()
            return MessageTaskManager.get()[self.target.targetId]['all'][self]['result']
        else:
            raise WaitCancelException

    async def sleep(self, s):
        ExecutionLockList.remove(self)
        await asyncio.sleep(s)

    def checkSuperUser(self):
        return True if self.target.senderInfo.query.isSuperUser else False


__all__ = ["MessageSession"]
