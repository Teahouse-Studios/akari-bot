import re
import traceback
import ujson as json
from typing import List, Union

import aiohttp
from khl import MessageTypes, Message

from bots.kook.client import bot, client_name
from config import Config
from core.builtins import Bot, Plain, Image, Voice, MessageSession as MS, ErrorMessage
from core.builtins.message.chain import MessageChain
from core.logger import Logger
from core.types import MsgInfo, Session, FetchTarget as FT, \
    FinishedSession as FinS
from core.utils.image import image_split
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
        self.session.message: Message
        msgchain = MessageChain(msgchain)
        if not msgchain.is_safe and not disable_secret_check:
            return await self.sendMessage(Plain(ErrorMessage(self.locale.t("error.message.chain.unsafe"))))
        self.sent.append(msgchain)
        count = 0
        send = []
        for x in msgchain.asSendable(embed=False):
            if isinstance(x, Plain):
                send_ = await self.session.message.reply(x.text, quote=quote if quote
                                                         and count == 0 and self.session.message else None)

                Logger.info(f'[Bot] -> [{self.target.targetId}]: {x.text}')
                send.append(send_)
                count += 1
            elif isinstance(x, Image):
                url = await bot.create_asset(open(await x.get(), 'rb'))
                send_ = await self.session.message.reply(url, type=MessageTypes.IMG, quote=quote if quote
                                                         and count == 0 and self.session.message else None)
                Logger.info(f'[Bot] -> [{self.target.targetId}]: Image: {str(x.__dict__)}')
                send.append(send_)
                count += 1
            elif isinstance(x, Voice):
                url = await bot.create_asset(open(x.path), 'rb')
                send_ = await self.session.message.reply(url, type=MessageTypes.AUDIO, quote=quote if quote
                                                         and count == 0 and self.session.message else None)
                Logger.info(f'[Bot] -> [{self.target.targetId}]: Voice: {str(x.__dict__)}')
                send.append(send_)
                count += 1

        msgIds = []
        for x in send:
            msgIds.append(x['msg_id'])
        return FinishedSession(self, msgIds, {self.session.message.channel_type.name: send})

    async def checkPermission(self):
        self.session.message: Message
        if self.session.message.channel_type.name == 'PERSON' or self.target.senderId in self.custom_admins \
                or self.target.senderInfo.query.isSuperUser:
            return True
        return await self.checkNativePermission()

    async def checkNativePermission(self):
        self.session.message: Message
        if self.session.message.channel_type.name == 'PERSON':
            return True
        guild = await bot.client.fetch_guild(self.session.message.ctx.guild.id)
        user_roles = (await guild.fetch_user(self.session.message.author.id)).roles
        guild_roles = await guild.fetch_roles()
        for i in guild_roles:  # 遍历服务器身分组
            if i.id in user_roles and i.has_permission(0):
                return True
        if self.session.message.author.id == guild.master_id:
            return True
        return False

    def asDisplay(self, text_only=False):
        if self.session.message.content:
            msg = re.sub(r'\[.*]\((.*)\)', '\\1', self.session.message.content)
            return msg
        return ''

    async def toMessageChain(self):
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

    class Typing:
        def __init__(self, msg: MS):
            self.msg = msg

        async def __aenter__(self):
            # await bot.answer_chat_action(self.msg.session.target, 'typing')
            pass

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass


class FetchedSession(Bot.FetchedSession):

    async def sendDirectMessage(self, msgchain, disable_secret_check=False, allow_split_image=True):
        if self.target.targetFrom == 'Kook|GROUP':
            get_channel = await bot.client.fetch_public_channel(self.session.target)
            if not get_channel:
                return False
        elif self.target.targetFrom == 'Kook|PERSON':
            get_channel = await bot.client.fetch_user(self.session.target)
            Logger.debug(f'get_channel: {get_channel}')
            if not get_channel:
                return False
        else:
            return False

        msgchain = MessageChain(msgchain)

        for x in msgchain.asSendable(embed=False):
            if isinstance(x, Plain):
                await get_channel.send(x.text)

                Logger.info(f'[Bot] -> [{self.target.targetId}]: {x.text}')
            elif isinstance(x, Image):
                url = await bot.create_asset(open(await x.get(), 'rb'))
                await get_channel.send(url, type=MessageTypes.IMG)
                Logger.info(f'[Bot] -> [{self.target.targetId}]: Image: {str(x.__dict__)}')
            elif isinstance(x, Voice):
                url = await bot.create_asset(open(x.path), 'rb')
                await get_channel.send(url, type=MessageTypes.AUDIO)
                Logger.info(f'[Bot] -> [{self.target.targetId}]: Voice: {str(x.__dict__)}')


Bot.FetchedSession = FetchedSession


class FetchTarget(FT):
    name = client_name

    @staticmethod
    async def fetch_target(targetId, senderId=None) -> Union[Bot.FetchedSession]:
        matchChannel = re.match(r'^(Kook\|.*?)\|(.*)', targetId)
        if matchChannel:
            targetFrom = senderFrom = matchChannel.group(1)
            if senderId:
                matchSender = re.match(r'^(Kook\|User)\|(.*)', senderId)
                if matchSender:
                    senderFrom = matchSender.group(1)
                    senderId = matchSender.group(2)
            else:
                targetId = senderId = matchChannel.group(2)

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
            get_target_id = BotDBUtil.TargetInfo.get_enabled_this(module_name, "Kook")
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
