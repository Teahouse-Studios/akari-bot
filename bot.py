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
from core.loader import rss_loader
from core.parser import parser
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
    kwargs = {MessageChain: message, Group: group, Member: member}
    await parser(kwargs)


@bcc.receiver('FriendMessage')
async def group_message_handler(message: MessageChain, friend: Friend):
    kwargs = {MessageChain: message, Friend: friend}
    await parser(kwargs)


@bcc.receiver("NewFriendRequestEvent")
async def NFriend(event: NewFriendRequestEvent):
    await event.accept()


@bcc.receiver("BotInvitedJoinGroupRequestEvent")
async def NGroup(event: BotInvitedJoinGroupRequestEvent):
    await event.accept()


@bcc.receiver('ApplicationLaunched')
async def message_handler(app: GraiaMiraiApplication):
    rss_list = rss_loader()
    gather_list = []
    for x in rss_list:
        gather_list.append(asyncio.ensure_future(rss_list[x](app)))
    await asyncio.gather(*gather_list)


@bcc.receiver('ApplicationLaunched')
async def legacy_message_handler(app: GraiaMiraiApplication):
    if Config().config('account') != '2052142661':
        await newbie(app)


app.launch_blocking()
