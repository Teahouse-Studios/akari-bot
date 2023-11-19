import asyncio
from datetime import datetime
from typing import List

from core.builtins.message.chain import *
from core.builtins.message.internal import *
from core.builtins.tasks import MessageTaskManager
from core.builtins.temp import ExecutionLockList
from core.builtins.utils import confirm_command
from core.exceptions import WaitCancelException
from core.types.message import MessageSession as MessageSessionT, MsgInfo, Session
from core.utils.i18n import Locale
from database import BotDBUtil


class MessageSession(MessageSessionT):
    def __init__(self,
                 target: MsgInfo,
                 session: Session):
        self.target = target
        self.session = session
        self.sent: List[MessageChain] = []
        self.prefixes: List[str] = []
        self.data = BotDBUtil.TargetInfo(self.target.target_id)
        self.muted = self.data.is_muted
        self.options = self.data.options
        self.custom_admins = self.data.custom_admins
        self.enabled_modules = self.data.enabled_modules
        self.locale = Locale(self.data.locale)
        self.timestamp = datetime.now()
        self.tmp = {}

    async def wait_confirm(self, message_chain=None, quote=True, delete=True, append_instruction=True) -> bool:
        send = None
        ExecutionLockList.remove(self)
        if message_chain is not None:
            message_chain = MessageChain(message_chain)
            if append_instruction:
                message_chain.append(Plain(self.locale.t("message.wait.confirm.prompt.type1")))
            send = await self.send_message(message_chain, quote)
        flag = asyncio.Event()
        MessageTaskManager.add_task(self, flag)
        await flag.wait()
        result = MessageTaskManager.get_result(self)
        if result is not None:
            if message_chain is not None and delete:
                await send.delete()
            if result.as_display(text_only=True) in confirm_command:
                return True
            return False
        else:
            raise WaitCancelException

    async def wait_next_message(self, message_chain=None, quote=True, delete=False,
                                append_instruction=True) -> MessageSessionT:
        sent = None
        ExecutionLockList.remove(self)
        if message_chain is not None:
            message_chain = MessageChain(message_chain)
            if append_instruction:
                message_chain.append(Plain(self.locale.t("message.wait.confirm.prompt.type2")))
            sent = await self.send_message(message_chain, quote)
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

    async def wait_reply(self, message_chain, quote=True, all_=False, append_instruction=True) -> MessageSessionT:
        self.tmp['enforce_send_by_master_client'] = True
        ExecutionLockList.remove(self)
        message_chain = MessageChain(message_chain)
        if append_instruction:
            message_chain.append(Plain(self.locale.t("message.reply.prompt")))
        send = await self.send_message(message_chain, quote)
        flag = asyncio.Event()
        MessageTaskManager.add_task(self, flag, reply=send.message_id, all_=all_)
        await flag.wait()
        result = MessageTaskManager.get_result(self)
        if result is not None:
            return result
        else:
            raise WaitCancelException

    async def wait_anyone(self, message_chain=None, delete=False) -> MessageSessionT:
        send = None
        ExecutionLockList.remove(self)
        if message_chain is not None:
            message_chain = MessageChain(message_chain)
            send = await self.send_message(message_chain, quote=False)
        flag = asyncio.Event()
        MessageTaskManager.add_task(self, flag, all_=True)
        await flag.wait()
        result = MessageTaskManager.get()[self.target.target_id]['all'][self]
        if 'result' in result:
            if send is not None and delete:
                await send.delete()
            return MessageTaskManager.get()[self.target.target_id]['all'][self]['result']
        else:
            raise WaitCancelException

    async def sleep(self, s):
        ExecutionLockList.remove(self)
        await asyncio.sleep(s)

    def check_super_user(self):
        return True if self.target.sender_info.query.isSuperUser else False

    async def check_permission(self):
        if self.target.sender_id in self.custom_admins or self.target.sender_info.query.isSuperUser:
            return True
        return await self.check_native_permission()

    waitConfirm = wait_confirm
    waitNextMessage = wait_next_message
    waitReply = wait_reply
    waitAnyone = wait_anyone
    checkPermission = check_permission
    checkSuperUser = check_super_user


__all__ = ["MessageSession"]
