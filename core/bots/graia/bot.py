import asyncio
import os
import shutil

from graia.application.event.mirai import NewFriendRequestEvent, BotInvitedJoinGroupRequestEvent
from graia.application.friend import Friend
from graia.application.group import Group, Member
from graia.application.message.chain import MessageChain
from graia.application import GraiaMiraiApplication

from config import Config
from core.logger import Logginglogger
from core.template import Template
from core.bots.graia.template import Template as BotTemplate
from core.bots.graia.broadcast import bcc, app
from core.elements import MsgInfo, MessageSession, Session
from core.loader import Modules
from core.parser.message import parser
from core.utils import load_prompt as lp


Template.bind_template(BotTemplate)


@bcc.receiver('GroupMessage')
async def group_message_handler(message: MessageChain, group: Group, member: Member):
    msg = MessageSession(target=MsgInfo(targetId=group.id, senderId=f'QQ|{member.id}', senderName=member.name,
                               msgFrom='QQ|Group'), session=Session(message=message, target=group, sender=member))
    await parser(msg)


@bcc.receiver('FriendMessage')
async def group_message_handler(message: MessageChain, friend: Friend):
    msg = MessageSession(target=MsgInfo(targetId=friend.id, senderId=f'QQ|{friend.id}', senderName=friend.name,
                               msgFrom='QQ|Group'), session=Session(message=message, target=friend, sender=friend))
    await parser(msg)


@bcc.receiver("NewFriendRequestEvent")
async def NFriend(event: NewFriendRequestEvent):
    await event.accept()


@bcc.receiver("BotInvitedJoinGroupRequestEvent")
async def NGroup(event: BotInvitedJoinGroupRequestEvent):
    await event.accept()


@bcc.receiver('ApplicationLaunched')
async def autorun_handler(app: GraiaMiraiApplication):
    gather_list = []
    for x in Modules:
        if Modules[x].autorun:
            gather_list.append(asyncio.ensure_future(Modules[x].function(app)))
    await asyncio.gather(*gather_list)


@bcc.receiver('ApplicationLaunched', priority=16)
async def load_prompt():
    await lp()


app.launch_blocking()
