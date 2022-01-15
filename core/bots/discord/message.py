import asyncio
import datetime
import re
import traceback
from typing import List, Union

import discord

from core.bots.discord.client import client
from core.elements import Plain, Image, MessageSession as MS, MsgInfo, Session, FetchTarget as FT, ExecutionLockList,\
    FetchedSession as FS, FinishedSession as FinS
from core.elements.message.chain import MessageChain
from core.elements.message.internal import Embed
from core.elements.others import confirm_command
from database import BotDBUtil


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
    def __init__(self, result: list):
        self.result = result

    async def delete(self):
        """
        用于删除这条消息。
        """
        try:
            for x in self.result:
                await x.delete()
        except Exception:
            traceback.print_exc()


class MessageSession(MS):
    class Feature:
        image = True
        voice = False
        forward = False
        delete = True

    async def sendMessage(self, msgchain, quote=True, disable_secret_check=False) -> FinishedSession:
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
                embeds, files = await convert_embed(x)
                send_ = await self.session.target.send(embed=embeds,
                                                       reference=self.session.message if quote and count == 0
                                                                                         and self.session.message else None,
                                                       files=files)
            else:
                send_ = False
            if send_:
                send.append(send_)
            count += 1
        return FinishedSession(send)

    async def waitConfirm(self, msgchain=None, quote=True):
        ExecutionLockList.remove(self)

        def check(m):
            return m.channel == self.session.message.channel and m.author == self.session.message.author

        send = None
        if msgchain is not None:
            msgchain = MessageChain(msgchain)
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
            for x in self.session.message:
                await x.delete()
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


class FetchedSession(FS):
    def __init__(self, targetFrom, targetId):
        self.target = MsgInfo(targetId=f'{targetFrom}|{targetId}',
                              senderId=f'{targetFrom}|{targetId}',
                              targetFrom=targetFrom,
                              senderFrom=targetFrom,
                              senderName='')
        self.session = Session(message=False, target=targetId, sender=targetId)
        self.parent = MessageSession(self.target, self.session)

    async def sendMessage(self, msgchain, disable_secret_check=False):
        """
        用于向获取对象发送消息。
        :param msgchain: 消息链，若传入str则自动创建一条带有Plain元素的消息链
        :param disable_secret_check: 是否禁用消息检查（默认为False）
        :return: 被发送的消息链
        """
        try:
            getChannel = await client.fetch_channel(self.session.target)
        except Exception:
            traceback.print_exc()
            return False
        self.session.target = self.session.sender = self.parent.session.target = self.parent.session.sender = getChannel
        return await self.parent.sendMessage(msgchain, disable_secret_check=disable_secret_check, quote=False)


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
    async def post_message(module_name, message, user_list: List[FetchedSession] = None):
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
                        send = await fetch.sendMessage(message)
                        send_list.append(send)
                    except Exception:
                        traceback.print_exc()
        return send_list
