import datetime
import re
import traceback
from typing import List, Union

import discord
import filetype

from bots.discord.client import client
from config import Config
from core.builtins import Bot, Plain, Image, MessageSession as MS
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import Embed, ErrorMessage, Voice
from core.logger import Logger
from core.types import MsgInfo, Session, FetchTarget as FT, \
    FetchedSession as FS, FinishedSession as FinS
from core.utils.http import download_to_cache
from database import BotDBUtil

enable_analytics = Config('enable_analytics')


async def convert_embed(embed: Embed):
    if isinstance(embed, Embed):
        files = []
        embeds = discord.Embed(title=embed.title if embed.title is not None else discord.Embed.Empty,
                               description=embed.description if embed.description is not None else discord.Embed.Empty,
                               color=embed.color if embed.color is not None else discord.Embed.Empty,
                               url=embed.url if embed.url is not None else discord.Embed.Empty,
                               timestamp=datetime.datetime.fromtimestamp(
                                   embed.timestamp) if embed.timestamp is not None else discord.Embed.Empty, )
        if embed.image is not None:
            upload = discord.File(await embed.image.get(), filename="image.png")
            files.append(upload)
            embeds.set_image(url="attachment://image.png")
        if embed.thumbnail is not None:
            upload = discord.File(await embed.thumbnail.get(), filename="thumbnail.png")
            files.append(upload)
            embeds.set_thumbnail(url="attachment://thumbnail.png")
        if embed.author is not None:
            embeds.set_author(name=embed.author)
        if embed.footer is not None:
            embeds.set_footer(text=embed.footer)
        if embed.fields is not None:
            for field in embed.fields:
                embeds.add_field(name=field.name, value=field.value, inline=field.inline)
        return embeds, files


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
        embed = True
        forward = False
        delete = True
        quote = True
        wait = True

    async def sendMessage(self, msgchain, quote=True, disable_secret_check=False, allow_split_image=True
                          ) -> FinishedSession:
        msgchain = MessageChain(msgchain)
        if not msgchain.is_safe and not disable_secret_check:
            return await self.sendMessage(Plain(ErrorMessage(self.locale.t("error.message.chain.unsafe"))))
        self.sent.append(msgchain)
        count = 0
        send = []
        for x in msgchain.asSendable():
            if isinstance(x, Plain):
                send_ = await self.session.target.send(x.text,
                                                       reference=self.session.message if quote and count == 0
                                                       and self.session.message else None)
                Logger.info(f'[Bot] -> [{self.target.targetId}]: {x.text}')
            elif isinstance(x, Image):
                send_ = await self.session.target.send(file=discord.File(await x.get()),
                                                       reference=self.session.message if quote and count == 0
                                                       and self.session.message else None)
                Logger.info(f'[Bot] -> [{self.target.targetId}]: Image: {str(x.__dict__)}')
            elif isinstance(x, Voice):
                send_ = await self.session.target.send(file=discord.File(x.path),
                                                       reference=self.session.message if quote and count == 0
                                                       and self.session.message else None)
                Logger.info(f'[Bot] -> [{self.target.targetId}]: Voice: {str(x.__dict__)}')

            elif isinstance(x, Embed):
                embeds, files = await convert_embed(x)
                send_ = await self.session.target.send(embed=embeds,
                                                       reference=self.session.message if quote and count == 0
                                                       and self.session.message else None,
                                                       files=files)
                Logger.info(f'[Bot] -> [{self.target.targetId}]: Embed: {str(x.__dict__)}')
            else:
                send_ = False
            if send_:
                send.append(send_)
            count += 1
        msgIds = []
        for x in send:
            msgIds.append(x.id)

        return FinishedSession(self, msgIds, send)

    async def checkPermission(self):
        if self.session.message.channel.permissions_for(self.session.message.author).administrator \
                or isinstance(self.session.message.channel, discord.DMChannel) \
                or self.target.senderInfo.query.isSuperUser \
                or self.target.senderId in self.custom_admins:
            return True
        return False

    async def checkNativePermission(self):
        if self.session.message.channel.permissions_for(self.session.message.author).administrator \
                or isinstance(self.session.message.channel, discord.DMChannel):
            return True
        return False

    async def toMessageChain(self):
        lst = []
        lst.append(Plain(self.session.message.content))
        for x in self.session.message.attachments:
            d = await download_to_cache(x.url)
            if filetype.is_image(d):
                lst.append(Image(d))
        return MessageChain(lst)

    def asDisplay(self, text_only=False):
        msg = self.session.message.content
        msg = re.sub(r'<@(.*?)>', r'Discord|Client|\1', msg)
        return msg

    async def delete(self):
        try:
            await self.session.message.delete()
        except Exception:
            Logger.error(traceback.format_exc())

    class Typing:
        def __init__(self, msg: MS):
            self.msg = msg

        async def __aenter__(self):
            async with self.msg.session.target.typing() as typing:
                return typing

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass


class FetchedSession(FS):
    def __init__(self, targetFrom, targetId):
        self.target = MsgInfo(targetId=f'{targetFrom}|{targetId}',
                              senderId=f'{targetFrom}|{targetId}',
                              targetFrom=targetFrom,
                              senderFrom=targetFrom,
                              senderName='', clientName='Discord', messageId=0, replyId=None)
        self.session = Session(message=False, target=targetId, sender=targetId)
        self.parent = MessageSession(self.target, self.session)

    async def sendDirectMessage(self, msgchain, disable_secret_check=False, allow_split_image=True):
        try:
            getChannel = await client.fetch_channel(self.session.target)
        except Exception:
            Logger.error(traceback.format_exc())
            return False
        self.session.target = self.session.sender = self.parent.session.target = self.parent.session.sender = getChannel
        return await self.parent.sendDirectMessage(msgchain, disable_secret_check=disable_secret_check)


class FetchTarget(FT):
    name = 'Discord'

    @staticmethod
    async def fetch_target(targetId) -> Union[FetchedSession, bool]:
        matchChannel = re.match(r'^(Discord\|(?:DM\||)Channel)\|(.*)', targetId)
        if matchChannel:
            return FetchedSession(matchChannel.group(1), matchChannel.group(2))
        else:
            return False

    @staticmethod
    async def fetch_target_list(targetList: list) -> List[FetchedSession]:
        lst = []
        for x in targetList:
            fet = await FetchTarget.fetch_target(x)
            if fet:
                lst.append(fet)
        return lst

    @staticmethod
    async def post_message(module_name, message, user_list: List[FetchedSession] = None, i18n=False, **kwargs):
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
