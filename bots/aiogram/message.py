import re
import traceback
from typing import List, Union

from bots.aiogram.client import dp, bot, token, client_name
from config import Config
from core.builtins import Bot, Plain, Image, Voice, MessageSession as MS, ErrorMessage
from core.builtins.message.chain import MessageChain
from core.logger import Logger
from core.types import MsgInfo, Session, FetchTarget as FT, \
    FinishedSession as FinS
from core.utils.image import image_split
from database import BotDBUtil

enable_analytics = Config('enable_analytics')


class FinishedSession(FinS):
    async def delete(self):
        """
        用于删除这条消息。
        """
        try:
            for x in self.result:
                await x.delete()
        except Exception:
            Logger.error(traceback.format_exc())


class MessageSession(MS):
    class Feature:
        image = True
        voice = True
        embed = False
        forward = False
        delete = True
        quote = True
        wait = True

    async def sendMessage(self, msgchain, quote=True, disable_secret_check=False,
                          allow_split_image=True) -> FinishedSession:
        msgchain = MessageChain(msgchain)
        if not msgchain.is_safe and not disable_secret_check:
            return await self.sendMessage(Plain(ErrorMessage(self.locale.t("error.message.chain.unsafe"))))
        self.sent.append(msgchain)
        count = 0
        send = []
        for x in msgchain.asSendable(embed=False):
            if isinstance(x, Plain):
                send_ = await bot.send_message(self.session.target, x.text,
                                               reply_to_message_id=self.session.message.message_id if quote
                                               and count == 0 and self.session.message else None)
                Logger.info(f'[Bot] -> [{self.target.targetId}]: {x.text}')
                send.append(send_)
                count += 1
            elif isinstance(x, Image):
                if allow_split_image:
                    split = await image_split(x)
                    for xs in split:
                        with open(await xs.get(), 'rb') as image:
                            send_ = await bot.send_photo(self.session.target, image,
                                                         reply_to_message_id=self.session.message.message_id
                                                         if quote
                                                         and count == 0
                                                         and self.session.message else None)
                            Logger.info(f'[Bot] -> [{self.target.targetId}]: Image: {str(xs.__dict__)}')
                            send.append(send_)
                            count += 1
                else:
                    with open(await x.get(), 'rb') as image:
                        send_ = await bot.send_photo(self.session.target, image,
                                                     reply_to_message_id=self.session.message.message_id
                                                     if quote
                                                     and count == 0
                                                     and self.session.message else None)
                        Logger.info(f'[Bot] -> [{self.target.targetId}]: Image: {str(x.__dict__)}')
                        send.append(send_)
                        count += 1
            elif isinstance(x, Voice):
                with open(x.path, 'rb') as voice:
                    send_ = await bot.send_audio(self.session.target, voice,
                                                 reply_to_message_id=self.session.message.message_id if quote
                                                 and count == 0 and self.session.message else None)
                    Logger.info(f'[Bot] -> [{self.target.targetId}]: Voice: {str(x.__dict__)}')
                    send.append(send_)
                    count += 1

        msgIds = []
        for x in send:
            msgIds.append(x.message_id)
        return FinishedSession(self, msgIds, send)

    async def checkNativePermission(self):
        if not self.session.message:
            chat = await dp.bot.get_chat(self.session.target)
        else:
            chat = self.session.message.chat
        if chat.type == 'private':
            return True
        admins = [member.user.id for member in await dp.bot.get_chat_administrators(chat.id)]
        if self.session.sender in admins:
            return True
        return False

    def asDisplay(self, text_only=False):
        if self.session.message.text:
            return self.session.message.text
        return ''

    async def toMessageChain(self):
        lst = []
        if self.session.message.photo:
            file = await bot.get_file(self.session.message.photo[-1]['file_id'])
            lst.append(Image(f'https://api.telegram.org/file/bot{token}/{file.file_path}'))
        if self.session.message.caption:
            lst.append(Plain(self.session.message.caption))
        if self.session.message.text:
            lst.append(Plain(self.session.message.text))
        return MessageChain(lst)

    async def delete(self):
        try:
            for x in self.session.message:
                await x.delete()
        except Exception:
            Logger.error(traceback.format_exc())

    class Typing:
        def __init__(self, msg: MS):
            self.msg = msg

        async def __aenter__(self):
            # await bot.answer_chat_action(self.msg.session.target, 'typing')
            pass

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass


class FetchTarget(FT):
    name = client_name

    @staticmethod
    async def fetch_target(targetId, senderId=None) -> Union[Bot.FetchedSession]:
        matchChannel = re.match(r'^(Telegram\|.*?)\|(.*)', targetId)

        if matchChannel:
            targetFrom = senderFrom = matchChannel.group(1)
            targetId = matchChannel.group(2)
            if senderId:
                matchSender = re.match(r'^(Telegram\|User)\|(.*)', senderId)
                if matchSender:
                    senderFrom = matchSender.group(1)
                    senderId = matchSender.group(2)
            else:
                senderId = targetId

            return Bot.FetchedSession(targetFrom, targetId, senderFrom, senderId)

    @staticmethod
    async def fetch_target_list(targetList: list) -> List[Bot.FetchedSession]:
        lst = []
        for x in targetList:
            fet = await FetchTarget.fetch_target(x)
            if fet:
                lst.append(fet)
        return lst

    @staticmethod
    async def post_message(module_name, message, user_list: List[Bot.FetchedSession] = None, i18n=False, **kwargs):
        if user_list is not None:
            for x in user_list:
                try:
                    if i18n:
                        await x.sendDirectMessage(x.parent.locale.t(message, **kwargs))

                    else:
                        await x.sendDirectMessage(message)
                    if enable_analytics:
                        BotDBUtil.Analytics(x).add('', module_name, 'schedule')
                except Exception:
                    Logger.error(traceback.format_exc())
        else:
            get_target_id = BotDBUtil.TargetInfo.get_enabled_this(module_name, "Telegram")
            for x in get_target_id:
                fetch = await FetchTarget.fetch_target(x.targetId)
                if fetch:
                    try:
                        if i18n:
                            await fetch.sendDirectMessage(fetch.parent.locale.t(message, **kwargs))

                        else:
                            await fetch.sendDirectMessage(message)
                        if enable_analytics:
                            BotDBUtil.Analytics(fetch).add('', module_name, 'schedule')
                    except Exception:
                        Logger.error(traceback.format_exc())


Bot.MessageSession = MessageSession
Bot.FetchTarget = FetchTarget
Bot.client_name = client_name
