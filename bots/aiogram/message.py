import re
import traceback
from typing import List, Union

from bots.aiogram.client import dp, bot, token
from bots.aiogram.info import client_name
from config import Config
from core.builtins import Bot, Plain, Image, Voice, MessageSession as MessageSessionT, ErrorMessage, MessageTaskManager
from core.builtins.message.chain import MessageChain
from core.logger import Logger
from core.types import FetchTarget as FetchTargetT, \
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


class MessageSession(MessageSessionT):
    class Feature:
        image = True
        voice = True
        embed = False
        forward = False
        delete = True
        quote = True
        wait = True

    async def send_message(self, message_chain, quote=True, disable_secret_check=False,
                           allow_split_image=True, callback=None) -> FinishedSession:
        message_chain = MessageChain(message_chain)
        if not message_chain.is_safe and not disable_secret_check:
            return await self.send_message(Plain(ErrorMessage(self.locale.t("error.message.chain.unsafe"))))
        self.sent.append(message_chain)
        count = 0
        send = []
        for x in message_chain.as_sendable(self, embed=False):
            if isinstance(x, Plain):
                send_ = await bot.send_message(self.session.target, x.text,
                                               reply_to_message_id=self.session.message.message_id if quote
                                               and count == 0 and self.session.message else None)
                Logger.info(f'[Bot] -> [{self.target.target_id}]: {x.text}')
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
                            Logger.info(f'[Bot] -> [{self.target.target_id}]: Image: {str(xs.__dict__)}')
                            send.append(send_)
                            count += 1
                else:
                    with open(await x.get(), 'rb') as image:
                        send_ = await bot.send_photo(self.session.target, image,
                                                     reply_to_message_id=self.session.message.message_id
                                                     if quote
                                                     and count == 0
                                                     and self.session.message else None)
                        Logger.info(f'[Bot] -> [{self.target.target_id}]: Image: {str(x.__dict__)}')
                        send.append(send_)
                        count += 1
            elif isinstance(x, Voice):
                with open(x.path, 'rb') as voice:
                    send_ = await bot.send_audio(self.session.target, voice,
                                                 reply_to_message_id=self.session.message.message_id if quote
                                                 and count == 0 and self.session.message else None)
                    Logger.info(f'[Bot] -> [{self.target.target_id}]: Voice: {str(x.__dict__)}')
                    send.append(send_)
                    count += 1

        msg_ids = []
        for x in send:
            msg_ids.append(x.message_id)
            if callback:
                MessageTaskManager.add_callback(x.message_id, callback)
        return FinishedSession(self, msg_ids, send)

    async def check_native_permission(self):
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

    def as_display(self, text_only=False):
        if self.session.message.text:
            return self.session.message.text
        return ''

    async def to_message_chain(self):
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

    sendMessage = send_message
    asDisplay = as_display
    toMessageChain = to_message_chain
    checkNativePermission = check_native_permission

    class Typing:
        def __init__(self, msg: MessageSessionT):
            self.msg = msg

        async def __aenter__(self):
            # await bot.answer_chat_action(self.msg.session.target, 'typing')
            pass

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass


class FetchTarget(FetchTargetT):
    name = client_name

    @staticmethod
    async def fetch_target(target_id, sender_id=None) -> Union[Bot.FetchedSession]:
        match_channel = re.match(r'^(Telegram\|.*?)\|(.*)', target_id)

        if match_channel:
            target_from = sender_from = match_channel.group(1)
            target_id = match_channel.group(2)
            if sender_id:
                match_sender = re.match(r'^(Telegram\|User)\|(.*)', sender_id)
                if match_sender:
                    sender_from = match_sender.group(1)
                    sender_id = match_sender.group(2)
            else:
                sender_id = target_id

            return Bot.FetchedSession(target_from, target_id, sender_from, sender_id)

    @staticmethod
    async def fetch_target_list(target_list: list) -> List[Bot.FetchedSession]:
        lst = []
        for x in target_list:
            fet = await FetchTarget.fetch_target(x)
            if fet:
                lst.append(fet)
        return lst

    @staticmethod
    async def post_message(module_name, message, user_list: List[Bot.FetchedSession] = None, i18n=False, **kwargs):
        if user_list is not None:
            for x in user_list:
                try:
                    msgchain = message
                    if isinstance(message, str):
                        if i18n:
                            msgchain = MessageChain([Plain(x.parent.locale.t(message, **kwargs))])
                        else:
                            msgchain = MessageChain([Plain(message)])
                    await x.send_direct_message(msgchain)
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
                        msgchain = message
                        if isinstance(message, str):
                            if i18n:
                                msgchain = MessageChain([Plain(fetch.parent.locale.t(message, **kwargs))])
                            else:
                                msgchain = MessageChain([Plain(message)])
                        await fetch.send_direct_message(msgchain)
                        if enable_analytics:
                            BotDBUtil.Analytics(fetch).add('', module_name, 'schedule')
                    except Exception:
                        Logger.error(traceback.format_exc())


Bot.MessageSession = MessageSession
Bot.FetchTarget = FetchTarget
Bot.client_name = client_name
