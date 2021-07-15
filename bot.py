import asyncio
import os
import shutil

from graia.application import GraiaMiraiApplication
from graia.application.event.mirai import NewFriendRequestEvent, BotInvitedJoinGroupRequestEvent
from graia.application.friend import Friend
from graia.application.group import Group, Member
from graia.application.message.chain import MessageChain

from core.broadcast import bcc, app
from core.elements import MsgInfo
from core.loader import Modules
from core.parser import parser
from core.utils import load_prompt as lp

cache_path = os.path.abspath('./cache/')
if os.path.exists(cache_path):
    shutil.rmtree(cache_path)
    os.mkdir(cache_path)
else:
    os.mkdir(cache_path)

version = os.path.abspath('.version')
write_version = open(version, 'w')
write_version.write(os.popen('git rev-parse HEAD', 'r').read()[0:7])
write_version.close()


@bcc.receiver('GroupMessage')
async def group_message_handler(message: MessageChain, group: Group, member: Member):
    kwargs = {MessageChain: message, Group: group, Member: member,
              MsgInfo: MsgInfo(fromId=f'QQ|{group.id}', fromName=group.name, senderId=f'QQ|{member.id}', senderName=member.name,
                               msgFrom=Group)}
    await parser(kwargs)


@bcc.receiver('FriendMessage')
async def group_message_handler(message: MessageChain, friend: Friend):
    kwargs = {MessageChain: message, Friend: friend,
              MsgInfo: MsgInfo(fromId=friend.id, fromName=friend.nickname, senderId=friend.id, senderName=friend.nickname,
                               msgFrom=Friend)}
    await parser(kwargs)


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
