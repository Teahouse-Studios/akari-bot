import asyncio
import logging
import os

import discord

from config import Config
from core.bots.discord.client import client
from core.bots.discord.message import MessageSession, FetchTarget
from core.elements import MsgInfo, Session, Schedule, StartUp, PrivateAssets, Url
from core.loader import ModulesManager
from core.logger import Logger
from core.parser.message import parser
from core.scheduler import Scheduler
from core.utils import init, load_prompt

PrivateAssets.set(os.path.abspath(os.path.dirname(__file__) + '/assets'))
init()
Url.completely_disable_mm = True

count = 0


@client.event
async def on_ready():
    Logger.info('Logged on as ' + str(client.user))
    global count
    if count == 0:
        gather_list = []
        Modules = ModulesManager.return_modules_list_as_dict()
        for x in Modules:
            if isinstance(Modules[x], StartUp):
                gather_list.append(asyncio.ensure_future(Modules[x].function(FetchTarget)))
            if isinstance(Modules[x], Schedule):
                Scheduler.add_job(func=Modules[x].function, trigger=Modules[x].trigger, args=[FetchTarget])
        await asyncio.gather(*gather_list)
        Scheduler.start()
        logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)
        await load_prompt(FetchTarget)
        count = 1


@client.event
async def on_message(message):
    # don't respond to ourselves
    if message.author == client.user:
        return
    target = "Discord|Channel"
    if isinstance(message.channel, discord.DMChannel):
        target = "Discord|DM|Channel"
    msg = MessageSession(target=MsgInfo(targetId=f"{target}|{message.channel.id}",
                                        senderId=f"Discord|Client|{message.author.id}",
                                        senderName=message.author.name, targetFrom=target, senderFrom="Discord|Client"),
                         session=Session(message=message, target=message.channel, sender=message.author))
    await parser(msg)


dc_token = Config('dc_token')
if dc_token:
    client.run(dc_token)
