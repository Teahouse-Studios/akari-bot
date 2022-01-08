import asyncio
import re
import traceback
from typing import List, Union

from core.bots.aiogram.client import dp, bot
from core.bots.aiogram.tasks import MessageTaskManager, FinishedTasks
from core.elements import Plain, Image, MessageSession as MS, MsgInfo, Session, Voice, FetchTarget as FT, \
    ExecutionLockList
from core.elements.message.chain import MessageChain
from core.elements.others import confirm_command
from database import BotDBUtil


def convert2lst(s) -> list:
    if isinstance(s, str):
        return [Plain(s)]
    elif isinstance(s, list):
        return s
    elif isinstance(s, tuple):
        return list(s)


class MessageSession(MS):
    class Feature:
        image = True
        voice = True
        forward = False
        delete = True

    async def sendMessage(self, msgchain, quote=True):
        msgchain = MessageChain(msgchain)
        if not msgchain.is_safe:
            return await self.sendMessage('https://wdf.ink/6Oup')
        count = 0
        send = []
        for x in msgchain.asSendable(embed=False):
            if isinstance(x, Plain):
                send_ = await bot.send_message(self.session.target, x.text,
                                               reply_to_message_id=self.session.message.message_id if quote
                                               and count == 0 and self.session.message else None)
            elif isinstance(x, Image):
                with open(await x.get(), 'rb') as image:
                    send_ = await bot.send_photo(self.session.target, image,
                                                 reply_to_message_id=self.session.message.message_id if quote
                                                 and count == 0
                                                 and self.session.message else None)
            elif isinstance(x, Voice):
                with open(x.path, 'rb') as voice:
                    send_ = await bot.send_audio(self.session.target, voice,
                                                 reply_to_message_id=self.session.message.message_id if quote
                                                 and count == 0 and self.session.message else None)
            else:
                send_ = False
            if send_:
                send.append(send_)
            count += 1
        return MessageSession(target=MsgInfo(targetId=0, senderId=0, senderName='', targetFrom='Telegram|Bot',
                                             senderFrom='Telegram|Bot'),
                              session=Session(message=send, target=send, sender=send))

    async def waitConfirm(self, msgchain=None, quote=True):
        ExecutionLockList.remove(self)
        send = None
        if msgchain is not None:
            msgchain = convert2lst(msgchain)
            msgchain.append(Plain('（发送“是”或符合确认条件的词语来确认）'))
            send = await self.sendMessage(msgchain, quote)
        flag = asyncio.Event()
        MessageTaskManager.add_task(self.session.sender, flag)
        await flag.wait()
        if msgchain is not None:
            await send.delete()
        if FinishedTasks.get()[self.session.sender].text in confirm_command:
            return True
        return False

    async def checkPermission(self):
        if self.session.message.chat.type == 'private' or self.target.senderInfo.check_TargetAdmin(
                self.target.targetId) or self.target.senderInfo.query.isSuperUser:
            return True
        admins = [member.user.id for member in await dp.bot.get_chat_administrators(self.session.message.chat.id)]
        if self.session.sender in admins:
            return True
        return False

    async def checkNativePermission(self):
        if self.session.message.chat.type == 'private':
            return True
        admins = [member.user.id for member in await dp.bot.get_chat_administrators(self.session.message.chat.id)]
        if self.session.sender in admins:
            return True
        return False

    def checkSuperUser(self):
        return True if self.target.senderInfo.query.isSuperUser else False

    def asDisplay(self):
        return self.session.message.text

    async def sleep(self, s):
        ExecutionLockList.remove(self)
        await asyncio.sleep(s)

    async def delete(self):
        try:
            if isinstance(self.session.message, list):
                for x in self.session.message:
                    await x.delete()
            else:
                await self.session.message.delete()
        except Exception:
            traceback.print_exc()

    class Typing:
        def __init__(self, msg: MS):
            self.msg = msg

        async def __aenter__(self):
            # await bot.answer_chat_action(self.msg.session.target, 'typing')
            pass

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass


class FetchTarget(FT):
    name = 'Telegram'

    @staticmethod
    async def fetch_target(targetId) -> Union[MessageSession, bool]:
        matchChannel = re.match(r'^(Telegram\|.*?)\|(.*)', targetId)
        if matchChannel:
            return MessageSession(MsgInfo(targetId=targetId, senderId=targetId, senderName='',
                                          targetFrom=matchChannel.group(1), senderFrom=matchChannel.group(1)),
                                  Session(message=False, target=matchChannel.group(2), sender=matchChannel.group(2)))
        else:
            return False

    @staticmethod
    async def fetch_target_list(targetList: list) -> List[MessageSession]:
        lst = []
        for x in targetList:
            fet = await FetchTarget.fetch_target(x)
            if fet:
                lst.append(fet)
        return lst

    @staticmethod
    async def post_message(module_name, message, user_list: List[MessageSession] = None):
        send_list = []
        if user_list is not None:
            for x in user_list:
                try:
                    send = await x.sendMessage(message, quote=False)
                    send_list.append(send)
                except Exception:
                    traceback.print_exc()
        else:
            get_target_id = BotDBUtil.Module.get_enabled_this(module_name)
            for x in get_target_id:
                fetch = await FetchTarget.fetch_target(x)
                if fetch:
                    try:
                        send = await fetch.sendMessage(message, quote=False)
                        send_list.append(send)
                    except Exception:
                        traceback.print_exc()
        return send_list
