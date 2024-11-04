import re
import traceback
from typing import Union

import filetype

from bots.ntqq.info import *
from core.builtins import Bot, Plain, Image, MessageSession as MessageSessionT, I18NContext, MessageTaskManager
from core.builtins.message.chain import MessageChain
from core.config import Config
from core.logger import Logger
from core.types import FetchTarget as FetchTargetT, \
    FinishedSession as FinS
from core.utils.http import download

enable_send_url = Config('qq_enable_send_url', False)


class FinishedSession(FinS):
    async def delete(self):
        """
        用于删除这条消息。
        """
        try:
            for x in self.result:
                await x._api.recall_message(channel_id=self.session.message.channel_id, message_id=x['id'], hidetip=True)
        except Exception:
            Logger.error(traceback.format_exc())


class MessageSession(MessageSessionT):
    class Feature:
        image = True
        voice = False
        embed = False
        forward = False
        delete = True
        quote = False
        wait = False

    async def send_message(self, message_chain, quote=False, disable_secret_check=False,
                           enable_parse_message=False, enable_split_image=False, callback=None) -> FinishedSession:
        message_chain = MessageChain(message_chain)
        if not message_chain.is_safe and not disable_secret_check:
            return await self.send_message(I18NContext("error.message.chain.unsafe"))

        plains = []
        images = []
        url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$\-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
        for x in message_chain.as_sendable(self, embed=False):
            if isinstance(x, Plain):
                plains.append(x)
            elif isinstance(x, Image):
                images.append(await x.get())
        sends = []
        if len(plains) != 0:
            msg = '\n'.join([x.text for x in plains]).strip()

            filtered_msg = []
            lines = msg.split('\n')
            for line in lines:
                if enable_send_url:
                    line = url_pattern.sub(r'str(Url("\1", use_mm=True))', line)
                elif url_pattern.findall(line):
                    continue
                filtered_msg.append(line)
            msg = '\n'.join(filtered_msg).strip()

            send = await self.session.message.reply(content=msg, file_image=i)
            Logger.info(f'[Bot] -> [{self.target.target_id}]: {x.text}')
        if len(images) != 0:
            for i in images:
                send = await self.session.message.reply(file_image=i)
                sends.append(send)
                Logger.info(f'[Bot] -> [{self.target.target_id}]: Image: {str(x.__dict__)}')

        msg_ids = []
        for x in sends:
            Logger.info(str(x))
            msg_ids.append(x['id'])
            if callback:
                MessageTaskManager.add_callback(x['id'], callback)
        return FinishedSession(self, msg_ids, sends)

    async def check_native_permission(self):
        info = self.session.message.member
        admins = ["2", "4"]
        for x in admins:
            if x in info.roles:
                return True
        return False

    async def to_message_chain(self):
        lst = []
        lst.append(Plain(self.session.message.content))
        for x in self.session.message.attachments:
            d = await download(x.url)
            if filetype.is_image(d):
                lst.append(Image(d))
        return MessageChain(lst)

    def as_display(self, text_only=False):
        msg = self.session.message.content
        msg = re.sub(r'<@(.*?)>', fr'{sender_tiny_name}|\1', msg)
        return msg

    async def delete(self):
        try:
            await self.session.message._api.recall_message(channel_id=self.session.message.channel_id, message_id=self.session.message.id, hidetip=True)
        except Exception:
            Logger.error(traceback.format_exc())
            return False

    sendMessage = send_message
    asDisplay = as_display
    toMessageChain = to_message_chain
    checkNativePermission = check_native_permission

    class Typing:
        def __init__(self, msg: MessageSessionT):
            self.msg = msg

        async def __aenter__(self):
            pass

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass


class FetchTarget(FetchTargetT):
    name = client_name

    @staticmethod
    async def fetch_target(target_id, sender_id=None) -> Union[Bot.FetchedSession]:
        target_pattern = r'|'.join(re.escape(item) for item in target_name_list)
        match_target = re.match(fr"({target_pattern})\|(.*)", target_id)
        if match_target:
            target_from = sender_from = match_target.group(1)
            target_id = match_target.group(2)
            if sender_id:
                sender_pattern = r'|'.join(re.escape(item) for item in sender_name_list)
                match_sender = re.match(fr'^({sender_pattern})\|(.*)', sender_id)
                if match_sender:
                    sender_from = match_sender.group(1)
                    sender_id = match_sender.group(2)
            else:
                sender_id = target_id

            return Bot.FetchedSession(target_from, target_id, sender_from, sender_id)


Bot.MessageSession = MessageSession
Bot.FetchTarget = FetchTarget
Bot.client_name = client_name
