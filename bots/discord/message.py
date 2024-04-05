import datetime
import re
import traceback
from typing import List, Union

import discord
import filetype

from bots.discord.client import client
from bots.discord.info import client_name
from config import Config
from core.builtins import Bot, Plain, Image, MessageSession as MessageSessionT, MessageTaskManager
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import Embed, ErrorMessage, Voice
from core.logger import Logger
from core.types import FetchTarget as FetchTargetT, FinishedSession as FinS
from core.utils.http import download_to_cache
from database import BotDBUtil

enable_analytics = Config('enable_analytics')


async def convert_embed(embed: Embed):
    if isinstance(embed, Embed):
        files = []
        embeds = discord.Embed(title=embed.title if embed.title else None,
                               description=embed.description if embed.description else None,
                               color=embed.color if embed.color else None,
                               url=embed.url if embed.url else None,
                               timestamp=datetime.datetime.fromtimestamp(
                                   embed.timestamp) if embed.timestamp else None, )
        if embed.image:
            upload = discord.File(await embed.image.get(), filename="image.png")
            files.append(upload)
            embeds.set_image(url="attachment://image.png")
        if embed.thumbnail:
            upload = discord.File(await embed.thumbnail.get(), filename="thumbnail.png")
            files.append(upload)
            embeds.set_thumbnail(url="attachment://thumbnail.png")
        if embed.author:
            embeds.set_author(name=embed.author)
        if embed.footer:
            embeds.set_footer(text=embed.footer)
        if embed.fields:
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


class MessageSession(MessageSessionT):
    class Feature:
        image = True
        voice = True
        embed = True
        forward = False
        delete = True
        quote = True
        wait = True

    async def send_message(self, message_chain, quote=True, disable_secret_check=False, allow_split_image=True,
                           callback=None
                           ) -> FinishedSession:
        message_chain = MessageChain(message_chain)
        if not message_chain.is_safe and not disable_secret_check:
            return await self.send_message(Plain(ErrorMessage(self.locale.t("error.message.chain.unsafe"))))
        self.sent.append(message_chain)
        count = 0
        send = []
        for x in message_chain.as_sendable(self):
            if isinstance(x, Plain):
                send_ = await self.session.target.send(x.text,
                                                       reference=self.session.message if quote and count == 0
                                                       and self.session.message else None)
                Logger.info(f'[Bot] -> [{self.target.target_id}]: {x.text}')
            elif isinstance(x, Image):
                send_ = await self.session.target.send(file=discord.File(await x.get()),
                                                       reference=self.session.message if quote and count == 0
                                                       and self.session.message else None)
                Logger.info(f'[Bot] -> [{self.target.target_id}]: Image: {str(x.__dict__)}')
            elif isinstance(x, Voice):
                send_ = await self.session.target.send(file=discord.File(x.path),
                                                       reference=self.session.message if quote and count == 0
                                                       and self.session.message else None)
                Logger.info(f'[Bot] -> [{self.target.target_id}]: Voice: {str(x.__dict__)}')

            elif isinstance(x, Embed):
                embeds, files = await convert_embed(x)
                send_ = await self.session.target.send(embed=embeds,
                                                       reference=self.session.message if quote and count == 0
                                                       and self.session.message else None,
                                                       files=files)
                Logger.info(f'[Bot] -> [{self.target.target_id}]: Embed: {str(x.__dict__)}')
            else:
                send_ = None
            if send_:
                send.append(send_)
            count += 1
        msg_ids = []
        for x in send:
            msg_ids.append(x.id)
            if callback:
                MessageTaskManager.add_callback(x.id, callback)

        return FinishedSession(self, msg_ids, send)

    async def check_native_permission(self):
        if not self.session.message:
            channel = await client.fetch_channel(self.session.target)
            author = await channel.guild.fetch_member(self.session.sender)
        else:
            channel = self.session.message.channel
            author = self.session.message.author
        try:
            if channel.permissions_for(author).administrator \
                    or isinstance(channel, discord.DMChannel):
                return True
        except Exception:
            Logger.error(traceback.format_exc())
        return False

    async def to_message_chain(self):
        lst = []
        lst.append(Plain(self.session.message.content))
        for x in self.session.message.attachments:
            d = await download_to_cache(x.url)
            if filetype.is_image(d):
                lst.append(Image(d))
        return MessageChain(lst)

    def as_display(self, text_only=False):
        msg = self.session.message.content
        msg = re.sub(r'<@(.*?)>', r'Discord|Client|\1', msg)
        return msg

    async def delete(self):
        try:
            await self.session.message.delete()
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
            async with self.msg.session.target.typing() as typing:
                return typing

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass


class FetchedSession(Bot.FetchedSession):

    async def send_direct_message(self, message_chain, disable_secret_check=False, allow_split_image=True):
        try:
            get_channel = await client.fetch_channel(self.session.target)
        except Exception:
            Logger.error(traceback.format_exc())
            return False
        self.session.target = self.session.sender = self.parent.session.target = self.parent.session.sender = get_channel
        return await self.parent.send_direct_message(message_chain, disable_secret_check=disable_secret_check)


Bot.FetchedSession = FetchedSession


class FetchTarget(FetchTargetT):
    name = client_name

    @staticmethod
    async def fetch_target(target_id, sender_id=None) -> Union[Bot.FetchedSession]:
        match_channel = re.match(r'^(Discord\|(?:DM\||)Channel)\|(.*)', target_id)
        if match_channel:
            target_from = sender_from = match_channel.group(1)
            target_id = match_channel.group(2)
            if sender_id:
                match_sender = re.match(r'^(Discord\|Client)\|(.*)', sender_id)
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
        if user_list:
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
            get_target_id = BotDBUtil.TargetInfo.get_enabled_this(module_name, "Discord")
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
