import asyncio
import datetime
import re
import traceback
from typing import List, Union

import discord

from core.bots.discord.client import client
from core.bots.discord.smms import SMMS
from core.elements import Plain, Image, MessageSession as MS, MsgInfo, Session, FetchTarget as FT, ExecutionLockList
from core.elements.message.chain import MessageChain
from core.elements.message.internal import Embed
from core.elements.others import confirm_command
from database import BotDBUtil


smms = SMMS()


def convert2lst(s) -> list:
    if isinstance(s, str):
        return [Plain(s)]
    elif isinstance(s, list):
        return s
    elif isinstance(s, tuple):
        return list(s)


async def convert_embed(embed: Embed) -> discord.Embed:
    if isinstance(embed, Embed):
        embeds = discord.Embed(title=embed.title if embed.title is not None else discord.Embed.Empty,
                               description=embed.description if embed.description is not None else discord.Embed.Empty,
                               color=embed.color if embed.color is not None else discord.Embed.Empty,
                               url=embed.url if embed.url is not None else discord.Embed.Empty,
                               timestamp=datetime.datetime.fromtimestamp(
                                   embed.timestamp) if embed.timestamp is not None else discord.Embed.Empty, )
        if embed.image is not None and smms.status:
            upload = await smms.upload(await embed.image.get())
            if upload:
                embeds.set_image(url=upload)
        if embed.thumbnail is not None:
            upload = await smms.upload(await embed.thumbnail.get())
            if upload:
                embeds.set_thumbnail(url=upload)
        if embed.author is not None:
            embeds.set_author(name=embed.author)
        if embed.footer is not None:
            embeds.set_footer(text=embed.footer)
        if embed.fields is not None:
            for field in embed.fields:
                embeds.add_field(name=field.name, value=field.value, inline=field.inline)
        return embeds


class MessageSession(MS):
    class Feature:
        image = True
        voice = False
        forward = False
        delete = True

    async def sendMessage(self, msgchain, quote=True, disable_secret_check=False):
        msgchain = MessageChain(msgchain)
        if not msgchain.is_safe and not disable_secret_check:
            return await self.sendMessage('https://wdf.ink/6Oup')
        count = 0
        send = []
        for x in msgchain.asSendable():
            if isinstance(x, Plain):
                send_ = await self.session.target.send(x.text,
                                                       reference=self.session.message if quote and count == 0
                                                                                         and self.session.message else None)
            elif isinstance(x, Image):
                send_ = await self.session.target.send(file=discord.File(await x.get()),
                                                       reference=self.session.message if quote and count == 0
                                                                                         and self.session.message else None)
            elif isinstance(x, Embed):
                send_ = await self.session.target.send(embed=await convert_embed(x),
                                                       reference=self.session.message if quote and count == 0
                                                                                         and self.session.message else None)
            else:
                send_ = False
            if send_:
                send.append(send_)
            count += 1
        return MessageSession(target=MsgInfo(targetId=0, senderId=0, senderName='', targetFrom='Discord|Bot',
                                             senderFrom='Discord|Bot'),
                              session=Session(message=send, target=self.session.target, sender=self.session.sender))

    async def waitConfirm(self, msgchain=None, quote=True):
        ExecutionLockList.remove(self)

        def check(m):
            return m.channel == self.session.message.channel and m.author == self.session.message.author

        send = None
        if msgchain is not None:
            msgchain = convert2lst(msgchain)
            msgchain.append(Plain('（发送“是”或符合确认条件的词语来确认）'))
            send = await self.sendMessage(msgchain, quote)
        msg = await client.wait_for('message', check=check)
        if send is not None:
            await send.delete()
        return True if msg.content in confirm_command else False

    async def checkPermission(self):
        if self.session.message.channel.permissions_for(self.session.message.author).administrator \
                or isinstance(self.session.message.channel, discord.DMChannel) \
                or self.target.senderInfo.query.isSuperUser \
                or self.target.senderInfo.check_TargetAdmin(self.target.targetId):
            return True
        return False

    async def checkNativePermission(self):
        if self.session.message.channel.permissions_for(self.session.message.author).administrator \
                or isinstance(self.session.message.channel, discord.DMChannel):
            return True
        return False

    def checkSuperUser(self):
        return True if self.target.senderInfo.query.isSuperUser else False

    def asDisplay(self):
        return self.session.message.content

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
            async with self.msg.session.target.typing() as typing:
                return typing

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass


class FetchTarget(FT):
    name = 'Discord'

    @staticmethod
    async def fetch_target(targetId) -> Union[MessageSession, bool]:
        matchChannel = re.match(r'^(Discord\|(?:DM\||)Channel)\|(.*)', targetId)
        if matchChannel:
            getChannel = await client.fetch_channel(int(matchChannel.group(2)))
            return MessageSession(MsgInfo(targetId=targetId, senderId=targetId, senderName='',
                                          targetFrom=matchChannel.group(1), senderFrom=matchChannel.group(1)),
                                  Session(message=False, target=getChannel, sender=getChannel))
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
                    send = await x.sendMessage(message)
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
