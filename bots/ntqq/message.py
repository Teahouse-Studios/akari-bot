import re
import traceback
from typing import List, Union

import filetype
from botpy.message import C2CMessage, DirectMessage, GroupMessage, Message
from botpy.types.message import Reference

from bots.ntqq.info import *
from core.builtins import Bot, Plain, Image, MessageSession as MessageSessionT, I18NContext, MessageTaskManager
from core.builtins.message.chain import MessageChain
from core.config import Config
from core.database import BotDBUtil
from core.logger import Logger
from core.types import FetchTarget as FetchTargetT, \
    FinishedSession as FinS
from core.utils.http import download

enable_analytics = Config('enable_analytics', False)
enable_send_url = Config('qq_bot_enable_send_url', False)


class FinishedSession(FinS):
    async def delete(self):
        """
        用于删除这条消息。
        """
        if self.session.target.target_from in [target_guild_name, target_direct_name]:
            try:
                from bots.ntqq.bot import client
                for x in self.message_id:
                    await client.api.recall_message(channel_id=self.session.target.target_id.split('|')[-1], message_id=x, hidetip=True)
            except Exception:
                Logger.error(traceback.format_exc())


class MessageSession(MessageSessionT):
    class Feature:
        image = True
        voice = False
        embed = False
        forward = False
        delete = True
        quote = True
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
                images.append(x)
        sends = []
        if len(plains + images) != 0:
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

            if isinstance(self.session.message, Message):
                image = await images[0].get() if images else None
                send = await self.session.message.reply(content=msg, file_image=image, message_reference=Reference(message_id=self.session.message.id) if quote and self.session.message else None)
            elif isinstance(self.session.message, DirectMessage):
                image = await images[0].get() if images else None
                send = await self.session.message.reply(content=msg, file_image=image, message_reference=Reference(message_id=self.session.message.id) if quote and self.session.message else None)
            elif isinstance(self.session.message, GroupMessage):
                #  不是很懂如何发图片orz..
                #                media = await self.session.message._api.post_group_file(group_openid=self.session.message.group_openid, file_type=1, url=image)
                # send = await self.session.message.reply(content=msg, media=media,
                # message_reference=Reference(message_id=self.session.message.id) if quote
                # and self.session.message else None)
                msg = '\n' + msg
                send = await self.session.message.reply(content=msg, message_reference=Reference(message_id=self.session.message.id) if quote and self.session.message else None)
            elif isinstance(self.session.message, C2CMessage):
                #  不是很懂如何发图片orz..
                send = await self.session.message.reply(content=msg, message_reference=Reference(message_id=self.session.message.id) if quote and self.session.message else None)

        if callback:
            MessageTaskManager.add_callback(send['id'], callback)
        return FinishedSession(self, send['id'], sends)

    async def check_native_permission(self):
        if isinstance(self.session.message, Message):
            info = self.session.message.member
            admins = ["2", "4"]
            for x in admins:
                if x in info.roles:
                    return True
        elif isinstance(self.session.message, DirectMessage):
            return True
        elif isinstance(self.session.message, GroupMessage):
            ...  # QQ群好像无法获取成员权限信息..
        elif isinstance(self.session.message, C2CMessage):
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
        msg = re.sub(r'<@(.*?)>', fr'{sender_name}|\1', msg)
        return msg

    async def delete(self):
        if self.session.target.target_from in [target_guild_name, target_direct_name]:
            try:
                await self.session.message._api.recall_message(channel_id=self.session.message.channel_id, message_id=self.session.message.id, hidetip=True)
                return True
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

    @staticmethod
    async def fetch_target_list(target_list: list) -> List[Bot.FetchedSession]:
        lst = []
        for x in target_list:
            fet = await FetchTarget.fetch_target(x)
            if fet:
                if BotDBUtil.TargetInfo(fet.target.target_id).is_muted:
                    continue
                lst.append(fet)
        return lst

    @staticmethod
    async def post_message(module_name, message, user_list: List[Bot.FetchedSession] = None, i18n=False, **kwargs):
        if user_list:
            for x in user_list:
                try:
                    msgchain = message
                    if isinstance(message, str):
                        if i18n:
                            msgchain = MessageChain([Plain(x.parent.locale.t(message, **kwargs))])
                        else:
                            msgchain = MessageChain([Plain(message)])
                    msgchain = MessageChain(msgchain)
                    await x.send_direct_message(msgchain)
                    if enable_analytics:
                        BotDBUtil.Analytics(x).add('', module_name, 'schedule')
                except Exception:
                    Logger.error(traceback.format_exc())
        else:
            get_target_id = BotDBUtil.TargetInfo.get_enabled_this(module_name, "QQ|Bot")
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
                        msgchain = MessageChain(msgchain)
                        await fetch.send_direct_message(msgchain)
                        if enable_analytics:
                            BotDBUtil.Analytics(fetch).add('', module_name, 'schedule')
                    except Exception:
                        Logger.error(traceback.format_exc())


Bot.MessageSession = MessageSession
Bot.FetchTarget = FetchTarget
