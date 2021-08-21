import asyncio
import re
import traceback

from core.bots.aiogram.client import dp, bot
from core.bots.aiogram.tasks import MessageTaskManager, FinishedTasks
from core.elements import Plain, Image, MessageSession as MS, MsgInfo, Session, Voice, FetchTarget as FT
from core.elements.others import confirm_command
from aiogram import types


class MessageSession(MS):
    class Feature:
        image = True
        voice = True

    async def sendMessage(self, msgchain, quote=True):
        if isinstance(msgchain, str):
            send = await bot.send_message(self.session.target, msgchain,
                                          reply_to_message_id=self.session.message.message_id if quote and self.session.message else None)
            return MessageSession(target=MsgInfo(targetId=0, senderId=0, senderName='', targetFrom='Telegram|Bot',
                                                 senderFrom='Telegram|Bot'),
                                  session=Session(message=send, target=send.chat.id, sender=send.from_user.id))
        if isinstance(msgchain, list):
            count = 0
            send_list = []
            for x in msgchain:
                if isinstance(x, Plain):
                    send = await bot.send_message(self.session.target, x.text,
                                                  reply_to_message_id=self.session.message.message_id if quote and self.session.message else None)
                    send_list.append(send)
                    count += 1
                if isinstance(x, Image):
                    with open(await x.get(), 'rb') as image:
                        send = await bot.send_photo(self.session.target, image,
                                                    reply_to_message_id=self.session.message.message_id if quote and self.session.message else None)
                        send_list.append(send)
                        count += 1
                if isinstance(x, Voice):
                    with open(x.path, 'rb') as voice:
                        send = await bot.send_audio(self.session.target, voice,
                                                    reply_to_message_id=self.session.message.message_id if quote and self.session.message else None)
            return MessageSession(target=MsgInfo(targetId=0, senderId=0, senderName='', targetFrom='Telegram|Bot',
                                                 senderFrom='Telegram|Bot'),
                                  session=Session(message=send_list, target=send.chat.id, sender=send.from_user.id))

    async def waitConfirm(self):
        flag = asyncio.Event()
        MessageTaskManager.add_task(self.session.sender, flag)
        await flag.wait()
        if FinishedTasks.get()[self.session.sender].text in confirm_command:
            return True
        return False

    async def checkPermission(self):
        if self.session.message.chat.type == 'private' or self.target.senderInfo.check_TargetAdmin(
                self.target.targetId):
            return True
        admins = [member.user.id for member in await dp.bot.get_chat_administrators(self.session.message.chat.id)]
        if self.session.sender in admins:
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
            await self.msg.session.message.answer_chat_action('typing')

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass


class FetchTarget(FT):
    @staticmethod
    async def fetch_target(targetId):
        matchChannel = re.match(r'^(Telegram\|.*?)\|(.*)', targetId)
        if matchChannel:
            return MessageSession(MsgInfo(targetId=targetId, senderId=targetId, senderName='',
                                          targetFrom=matchChannel.group(1), senderFrom=matchChannel.group(1)),
                                  Session(message=False, target=matchChannel.group(2), sender=matchChannel.group(2)))
        else:
            return False
