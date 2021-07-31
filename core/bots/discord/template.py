import traceback

import discord
from core.elements import Plain, Image, MessageSession, MsgInfo, Session
from core.bots.discord.client import client
from core.elements.others import confirm_command


class Template(MessageSession):
    all_func = ("Feature", "sendMessage", "waitConfirm", "asDisplay", "delete", "checkPermission", "Typing", "checkSuperUser")

    class Feature:
        image = True
        voice = False

    async def sendMessage(self, msgchain, quote=True):
        if isinstance(msgchain, str):
            if msgchain == '':
                msgchain = '发生错误：机器人尝试发送空文本消息，请联系机器人开发者解决问题。'
            send = await self.session.message.channel.send(msgchain, reference=self.session.message if quote else None)
            return MessageSession(target=MsgInfo(targetId=0, senderId=0, senderName='', targetFrom='Discord|Bot', senderFrom='Discord|Bot'),
                                  session=Session(message=send, target=send.channel, sender=send.author))
        if isinstance(msgchain, list):
            count = 0
            send_list = []
            for x in msgchain:
                if isinstance(x, Plain):
                    send = await self.session.message.channel.send(x.text, reference=self.session.message if quote and count == 0 else None)
                if isinstance(x, Image):
                    send = await self.session.message.channel.send(file=discord.File(x.image), reference=self.session.message if quote and count == 0 else None)
                send_list.append(send)
                count += 1
            return MessageSession(target=MsgInfo(targetId=0, senderId=0, senderName='', targetFrom='Discord|Bot', senderFrom='Discord|Bot'),
                                  session=Session(message=send_list, target=send.channel, sender=send.author))

    async def waitConfirm(self):
        def check(m):
            return m.channel == self.session.message.channel and m.author == self.session.message.author

        msg = await client.wait_for('message', check=check)
        return True if msg.content in confirm_command else False

    def checkPermission(self):
        if self.session.message.channel.permissions_for(self.session.message.author).administrator\
                or isinstance(self.session.message.channel, discord.DMChannel)\
                or self.target.senderInfo.query.isSuperUser \
                or self.target.senderInfo.check_TargetAdmin(self.target.targetId):
            return True
        return False

    def checkSuperUser(self):
        return True if self.target.senderInfo.query.isSuperUser else False

    def asDisplay(self):
        return self.session.message.content

    async def delete(self):
        try:
            if isinstance(self.session.message, list):
                for x in self.session.message:
                    await x.delete()
            else:
                await self.session.message.delete()
        except:
            traceback.print_exc()

    class Typing:
        def __init__(self, msg: MessageSession):
            self.msg = msg

        async def __aenter__(self):
            async with self.msg.session.message.channel.typing() as typing:
                return typing

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass