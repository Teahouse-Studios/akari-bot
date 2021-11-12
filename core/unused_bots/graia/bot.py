import asyncio
import logging
import os

from graia.application.event.mirai import NewFriendRequestEvent, BotInvitedJoinGroupRequestEvent
from graia.application.friend import Friend
from graia.application.group import Group, Member
from graia.application.message.chain import MessageChain

from config import Config
from core.elements import MsgInfo, Session, Command, Schedule, PrivateAssets
from core.loader import ModulesManager
from core.parser.message import parser
from core.scheduler import Scheduler
from core.unused_bots.graia.broadcast import bcc, app
from core.unused_bots.graia.message import MessageSession, FetchTarget
from core.utils import init, load_prompt

PrivateAssets.set(os.path.abspath(os.path.dirname(__file__) + '/assets'))
init()


@bcc.receiver('GroupMessage')
async def group_message_handler(message: MessageChain, group: Group, member: Member):
    msg = MessageSession(
        target=MsgInfo(targetId=f"QQ|Group|{group.id}", senderId=f'QQ|{member.id}', senderName=member.name,
                       targetFrom='QQ|Group', senderFrom="QQ"),
        session=Session(message=message, target=group, sender=member))
    await parser(msg)


@bcc.receiver('FriendMessage')
async def friend_message_handler(message: MessageChain, friend: Friend):
    msg = MessageSession(
        target=MsgInfo(targetId=f"QQ|{friend.id}", senderId=f'QQ|{friend.id}', senderName=friend.nickname,
                       targetFrom='QQ', senderFrom='QQ'),
        session=Session(message=message, target=friend, sender=friend))
    await parser(msg)


@bcc.receiver("NewFriendRequestEvent")
async def new_friend(event: NewFriendRequestEvent):
    await event.accept()


@bcc.receiver("BotInvitedJoinGroupRequestEvent")
async def new_group(event: BotInvitedJoinGroupRequestEvent):
    await event.accept()


@bcc.receiver('ApplicationLaunched')
async def autorun_handler():
    gather_list = []
    Modules = ModulesManager.return_modules_list_as_dict()
    for x in Modules:
        if isinstance(Modules[x], Command) and Modules[x].autorun:
            gather_list.append(asyncio.ensure_future(Modules[x].function(FetchTarget)))
        if isinstance(Modules[x], Schedule):
            Scheduler.add_job(func=Modules[x].function, trigger=Modules[x].trigger, args=[FetchTarget])
    await asyncio.gather(*gather_list)
    Scheduler.start()
    logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)
    await load_prompt(FetchTarget)


if Config('qq_host') and Config('qq_account'):
    app.launch_blocking()
