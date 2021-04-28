import asyncio
import os
import shutil

from graia.application import GraiaMiraiApplication
from graia.application.event.mirai import NewFriendRequestEvent, BotInvitedJoinGroupRequestEvent
from graia.application.friend import Friend
from graia.application.group import Group, Member
from graia.application.message.chain import MessageChain

from config import Config
from core.broadcast import bcc, app
from core.elements import Target
from core.loader import Modules
from core.parser import parser
from core.utils import load_prompt as lp
from legacy_subbot import newbie

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
              Target: Target(id=group.id, senderId=member.id, name=group.name, target_from='Group')}
    await parser(kwargs)


@bcc.receiver('FriendMessage')
async def group_message_handler(message: MessageChain, friend: Friend):
    kwargs = {MessageChain: message, Friend: friend,
              Target: Target(id=friend.id, senderId=friend.id, name=friend.nickname, target_from='Friend')}
    await parser(kwargs)


@bcc.receiver("NewFriendRequestEvent")
async def NFriend(event: NewFriendRequestEvent):
    await event.accept()


@bcc.receiver("BotInvitedJoinGroupRequestEvent")
async def NGroup(event: BotInvitedJoinGroupRequestEvent):
    await event.accept()


@bcc.receiver('ApplicationLaunched')
async def message_handler(app: GraiaMiraiApplication):
    rss_list = Modules['rss']
    gather_list = []
    for x in rss_list:
        gather_list.append(asyncio.ensure_future(rss_list[x](app)))
    await asyncio.gather(*gather_list)


@bcc.receiver('ApplicationLaunched')
async def legacy_message_handler(app: GraiaMiraiApplication):
    if Config('account') != '2052142661':
        await newbie(app)

@bcc.receiver('ApplicationLaunched', priority=16)
async def load_prompt(app: GraiaMiraiApplication):
    await lp()


app.launch_blocking()
