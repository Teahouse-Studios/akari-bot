import re
import traceback
from typing import List, Union

import aiohttp
import ujson as json
from khl import MessageTypes, Message

from bots.kook.client import bot
from bots.kook.info import client_name
from config import Config
from core.builtins import Bot, Plain, Image, Voice, MessageSession as MessageSessionT, ErrorMessage
from core.builtins.message.chain import MessageChain
from core.logger import Logger
from core.types import FetchTarget as FetchTargetT, \
    FinishedSession as FinS
from database import BotDBUtil

enable_analytics = Config('enable_analytics')
kook_base = "https://www.kookapp.cn"
kook_headers = {f'Authorization': f"Bot {Config('kook_token')}"}


async def direct_msg_delete(msg_id: str):
    """删除私聊消息"""
    url = kook_base + "/api/v3/direct-message/delete"
    params = {"msg_id": msg_id}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=params, headers=kook_headers) as response:
            res = json.loads(await response.text())
    return res


async def channel_msg_delete(msg_id: str):
    """删除普通消息"""
    url = kook_base + "/api/v3/message/delete"
    params = {"msg_id": msg_id}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=params, headers=kook_headers) as response:
            res = json.loads(await response.text())
    return res


class FinishedSession(FinS):
    async def delete(self):
        """
        用于删除这条消息。
        """
        try:
            for x in self.result:
                for y in self.result[x]:
                    if x == 'PERSON':
                        await direct_msg_delete(y['msg_id'])
                    else:
                        await channel_msg_delete(y['msg_id'])
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
                           allow_split_image=True) -> FinishedSession:
        self.session.message: Message
        message_chain = MessageChain(message_chain)
        if not message_chain.is_safe and not disable_secret_check:
            return await self.send_message(Plain(ErrorMessage(self.locale.t("error.message.chain.unsafe"))))
        self.sent.append(message_chain)
        count = 0
        send = []
        for x in message_chain.as_sendable(self, embed=False):
            if isinstance(x, Plain):
                send_ = await self.session.message.reply(x.text, quote=quote if quote
                                                         and count == 0 and self.session.message else None)

                Logger.info(f'[Bot] -> [{self.target.target_id}]: {x.text}')
                send.append(send_)
                count += 1
            elif isinstance(x, Image):
                url = await bot.create_asset(open(await x.get(), 'rb'))
                send_ = await self.session.message.reply(url, type=MessageTypes.IMG, quote=quote if quote
                                                         and count == 0 and self.session.message else None)
                Logger.info(f'[Bot] -> [{self.target.target_id}]: Image: {str(x.__dict__)}')
                send.append(send_)
                count += 1
            elif isinstance(x, Voice):
                url = await bot.create_asset(open(x.path), 'rb')
                send_ = await self.session.message.reply(url, type=MessageTypes.AUDIO, quote=quote if quote
                                                         and count == 0 and self.session.message else None)
                Logger.info(f'[Bot] -> [{self.target.target_id}]: Voice: {str(x.__dict__)}')
                send.append(send_)
                count += 1

        msg_ids = []
        for x in send:
            msg_ids.append(x['msg_id'])
        return FinishedSession(self, msg_ids, {self.session.message.channel_type.name: send})

    async def check_native_permission(self):
        self.session.message: Message
        if not self.session.message:
            channel = await bot.client.fetch_public_channel(self.session.target)
            author = self.session.sender
        else:
            channel = await bot.client.fetch_public_channel(self.session.message.ctx.channel.id)
            author = self.session.message.author.id
        if channel.name == 'PERSON':
            return True
        guild = await bot.client.fetch_guild(channel.guild_id)
        user_roles = (await guild.fetch_user(author)).roles
        guild_roles = await guild.fetch_roles()
        for i in guild_roles:  # 遍历服务器身分组
            if i.id in user_roles and i.has_permission(0):
                return True
        if author == guild.master_id:
            return True
        return False

    def as_display(self, text_only=False):
        if self.session.message.content:
            msg = re.sub(r'\[.*]\((.*)\)', '\\1', self.session.message.content)
            return msg
        return ''

    async def to_message_chain(self):
        lst = []
        if self.session.message.type == MessageTypes.TEXT:
            lst.append(Plain(self.session.message.content))
        elif self.session.message.type == MessageTypes.IMG:
            lst.append(Image(self.session.message.content))
        elif self.session.message.type == MessageTypes.AUDIO:
            lst.append(Voice(self.session.message.content))
        return MessageChain(lst)

    async def delete(self):
        self.session.message: Message
        try:
            if self.session.message.channel_type.name == 'PERSON':
                await direct_msg_delete(self.session.message.id)
            else:
                await channel_msg_delete(self.session.message.id)
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


class FetchedSession(Bot.FetchedSession):

    async def send_direct_message(self, message_chain, disable_secret_check=False, allow_split_image=True):
        if self.target.target_from == 'Kook|GROUP':
            get_channel = await bot.client.fetch_public_channel(self.session.target)
            if not get_channel:
                return False
        elif self.target.target_from == 'Kook|PERSON':
            get_channel = await bot.client.fetch_user(self.session.target)
            Logger.debug(f'get_channel: {get_channel}')
            if not get_channel:
                return False
        else:
            return False

        message_chain = MessageChain(message_chain)

        for x in message_chain.as_sendable(self, embed=False):
            if isinstance(x, Plain):
                await get_channel.send(x.text)

                Logger.info(f'[Bot] -> [{self.target.target_id}]: {x.text}')
            elif isinstance(x, Image):
                url = await bot.create_asset(open(await x.get(), 'rb'))
                await get_channel.send(url, type=MessageTypes.IMG)
                Logger.info(f'[Bot] -> [{self.target.target_id}]: Image: {str(x.__dict__)}')
            elif isinstance(x, Voice):
                url = await bot.create_asset(open(x.path), 'rb')
                await get_channel.send(url, type=MessageTypes.AUDIO)
                Logger.info(f'[Bot] -> [{self.target.target_id}]: Voice: {str(x.__dict__)}')


Bot.FetchedSession = FetchedSession


class FetchTarget(FetchTargetT):
    name = client_name

    @staticmethod
    async def fetch_target(target_id, sender_id=None) -> Union[Bot.FetchedSession]:
        match_channel = re.match(r'^(Kook\|.*?)\|(.*)', target_id)
        if match_channel:
            target_from = sender_from = match_channel.group(1)
            target_id = match_channel.group(2)
            if sender_id:
                match_sender = re.match(r'^(Kook\|User)\|(.*)', sender_id)
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
                    if i18n:
                        await x.send_direct_message(x.parent.locale.t(message, **kwargs))

                    else:
                        await x.send_direct_message(message)
                    if enable_analytics:
                        BotDBUtil.Analytics(x).add('', module_name, 'schedule')
                except Exception:
                    Logger.error(traceback.format_exc())
        else:
            get_target_id = BotDBUtil.TargetInfo.get_enabled_this(module_name, "Kook")
            for x in get_target_id:
                fetch = await FetchTarget.fetch_target(x.targetId)
                if fetch:
                    try:
                        if i18n:
                            await fetch.send_direct_message(fetch.parent.locale.t(message, **kwargs))

                        else:
                            await fetch.send_direct_message(message)
                        if enable_analytics:
                            BotDBUtil.Analytics(fetch).add('', module_name, 'schedule')
                    except Exception:
                        Logger.error(traceback.format_exc())


Bot.MessageSession = MessageSession
Bot.FetchTarget = FetchTarget
