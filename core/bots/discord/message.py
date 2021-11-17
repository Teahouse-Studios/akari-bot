import asyncio
import re
import traceback
from typing import List

import discord

from core.bots.discord.client import client
from core.elements import Plain, Image, MessageSession as MS, MsgInfo, Session, FetchTarget as FT, ExecutionLockList
from core.elements.others import confirm_command
from core.secret_check import Secret
from database import BotDBUtil


def convert2lst(s) -> list:
    if isinstance(s, str):
        return [Plain(s)]
    elif isinstance(s, list):
        return s
    elif isinstance(s, tuple):
        return list(s)


class MessageSession(MS):
    class Feature:
        image = True
        voice = False
        forward = False
        delete = True

    async def sendMessage(self, msgchain, quote=True):
        if Secret.find(msgchain):
            return await self.sendMessage('https://wdf.ink/6Oup')
        if isinstance(msgchain, str):
            if msgchain == '':
                msgchain = '发生错误：机器人尝试发送空文本消息，请联系机器人开发者解决问题。\n错误汇报地址：https://github.com/Teahouse-Studios/bot/issues/new?assignees=OasisAkari&labels=bug&template=5678.md&title='
            send = await self.session.target.send(msgchain,
                                                  reference=self.session.message if quote and self.session.message else None)
        elif isinstance(msgchain, (list, tuple)):
            count = 0
            send = []
            for x in msgchain:
                if isinstance(x, Plain):
                    send_ = await self.session.target.send(x.text,
                                                           reference=self.session.message if quote and count == 0
                                                                                             and self.session.message else None)
                elif isinstance(x, Image):
                    send_ = await self.session.target.send(file=discord.File(await x.get()),
                                                           reference=self.session.message if quote and count == 0
                                                                                             and self.session.message else None)
                else:
                    send_ = False
                if send_:
                    send.append(send_)
                count += 1
        else:
            msgchain = '发生错误：机器人尝试发送非法消息链，请联系机器人开发者解决问题。\n错误汇报地址：https://github.com/Teahouse-Studios/bot/issues/new?assignees=OasisAkari&labels=bug&template=5678.md&title='
            send = await self.session.target.send(msgchain,
                                                  reference=self.session.message if quote and self.session.message else None)
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
    @staticmethod
    async def fetch_target(targetId) -> MessageSession:
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
