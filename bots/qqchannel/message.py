import asyncio
import re

from core.builtins.message import MessageSession as MS
from core.elements import FinishedSession as FinS, Plain, Image, ExecutionLockList, confirm_command
from core.elements.message.chain import MessageChain
from core.exceptions import WaitCancelException
from core.utils import MessageTaskManager


class FinishedSession(FinS):
    async def delete(self):
        """
        用于删除这条消息。
        """
        ...


class MessageSession(MS):

    async def sendMessage(self,
                          msgchain) -> FinishedSession:
        """
        用于向消息发送者回复消息。
        :param msgchain: 消息链，若传入str则自动创建一条带有Plain元素的消息链
        :return: 被发送的消息链
        """
        ...
        msgchain = MessageChain(msgchain)
        plains = []
        images = []
        for x in msgchain.asSendable(embed=False):
            if isinstance(x, Plain):
                plains.append(x)
            elif isinstance(x, Image):
                images.append(await x.get())
        sends = []
        if len(plains) != 0:
            msg = '\n'.join([x.text for x in plains])
            send = await self.session.message.reply(content=msg)
        if len(images) != 0:
            for i in images:
                send = await self.session.message.reply(file_image=i)
                sends.append(send)
        return FinishedSession([x['id'] for x in sends], sends)

    async def waitConfirm(self, msgchain=None, quote=True, delete=True) -> bool:
        send = None
        ExecutionLockList.remove(self)
        if msgchain is not None:
            msgchain = MessageChain(msgchain)
            msgchain.append(Plain('（请以“是”或符合确认条件的词语回复本条消息来确认）'))
            send = await self.sendMessage(msgchain)
        flag = asyncio.Event()
        MessageTaskManager.add_task(self, flag)
        await flag.wait()
        result = MessageTaskManager.get_result(self)
        if result:
            if result.asDisplay() in confirm_command:
                return True
            return False
        else:
            raise WaitCancelException

    async def waitNextMessage(self, msgchain=None, quote=True, delete=False):
        await self.waitConfirm(msgchain, quote, delete)

    async def waitReply(self, msgchain, quote=True):
        ExecutionLockList.remove(self)
        msgchain = MessageChain(msgchain)
        msgchain.append(Plain('（请使用指定的词语回复本条消息）'))
        send = await self.sendMessage(msgchain)
        flag = asyncio.Event()
        MessageTaskManager.add_task(self, flag, reply=send.messageId)
        await flag.wait()
        result = MessageTaskManager.get_result(self)
        if result:
            return result
        else:
            raise WaitCancelException

    async def waitAnyone(self, msgchain=None, delete=False):
        send = None
        ExecutionLockList.remove(self)
        if msgchain is not None:
            msgchain = MessageChain(msgchain)
            msgchain.append(Plain('（请使用指定的词语回复本条消息）'))
            send = await self.sendMessage(msgchain)
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

    def asDisplay(self):
        """
        用于将消息转换为一般文本格式。
        """
        return re.sub(r'^<@.*?>(.*)', '\\1', self.session.message.content).strip()

    async def delete(self):
        """
        用于删除这条消息。
        """
        ...

    async def checkPermission(self):
        """
        用于检查消息发送者在对象内的权限。
        """
        if self.target.senderInfo.check_TargetAdmin(self.target.targetId) \
            or self.target.senderInfo.query.isSuperUser:
            return True
        return await self.checkNativePermission()

    async def checkNativePermission(self):
        """
        用于检查消息发送者原本在聊天平台中是否具有管理员权限。
        """
        info = self.session.message.member.roles
        admins = ["2", "4"]
        for x in admins:
            if x in info.roles:
                return True
        return False

    def checkSuperUser(self):
        """
        用于检查消息发送者是否为超级用户。
        """
        return True if self.target.senderInfo.query.isSuperUser else False

    class Typing:
        def __init__(self, msg: MS):
            self.msg = msg

        async def __aenter__(self):
            pass

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    class Feature:
        """
        此消息来自的客户端所支持的消息特性一览，用于不同平台适用特性判断（如QQ支持消息类型的语音而Discord不支持）
        """
        image = False
        voice = False
        embed = False
        forward = False
        delete = False
        quote = False
        wait = False
