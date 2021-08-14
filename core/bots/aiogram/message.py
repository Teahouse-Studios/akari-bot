import re
import traceback

from core.bots.aiogram.client import dp
from core.elements import Plain, Image, MessageSession as MS, MsgInfo, Session
from core.elements.others import confirm_command
from aiogram import types, filters


class MessageSession(MS):
    class Feature:
        image = True
        voice = False

    async def sendMessage(self, msgchain, quote=True):
        if isinstance(msgchain, str):
            send = await self.session.message.answer(msgchain, reply=True if quote else False)
            return MessageSession(target=MsgInfo(targetId=0, senderId=0, senderName='', targetFrom='Telegram|Bot',
                                                 senderFrom='Telegram|Bot'),
                                  session=Session(message=send, target=send.chat.id, sender=send.from_user.id))
        if isinstance(msgchain, list):
            count = 0
            send_list = []
            for x in msgchain:
                if isinstance(x, Plain):
                    send = await self.session.message.answer(x.text)
                    send_list.append(send)
                    count += 1
                if isinstance(x, Image):
                    with open(await x.get(), 'rb') as image:
                        send = await self.session.message.reply_photo(image)
                        send_list.append(send)
                        count += 1
            return MessageSession(target=MsgInfo(targetId=0, senderId=0, senderName='', targetFrom='Telegram|Bot',
                                                 senderFrom='Telegram|Bot'),
                                  session=Session(message=send_list, target=send.chat.id, sender=send.chat.username))

    async def waitConfirm(self):
        return False

    async def checkPermission(self):
        if self.session.message.chat.type == 'private' or self.target.senderInfo.check_TargetAdmin(self.target.targetId):
            return True
        admins = [member.user.id for member in await dp.bot.get_chat_administrators(self.session.message.chat.id)]
        if self.session.sender.id in admins:
            return True
        return False

    def checkSuperUser(self):
        return True if self.target.senderInfo.query.isSuperUser else False

    def asDisplay(self):
        return self.session.message.text

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
        def __init__(self, msg: MS):
            self.msg = msg

        async def __aenter__(self):
            pass

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass


class FetchTarget:
    @staticmethod
    def fetch_target(targetId):
        matchChannel = re.match(r'^(DC|(?:DM\||)Channel)|(.*)', targetId)
        if matchChannel:
            getChannel = client.get_channel(int(matchChannel.group(2)))
            return MessageSession(MsgInfo(targetId=targetId, senderId=targetId, senderName='',
                                          targetFrom=matchChannel.group(1), senderFrom=matchChannel.group(1)),
                                  Session(message=False, target=getChannel, sender=getChannel))
        else:
            return False