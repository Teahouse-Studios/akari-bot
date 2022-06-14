import os

import discord

from bots.discord.client import client
from bots.discord.message import MessageSession, FetchTarget
from config import Config
from core.elements import MsgInfo, Session, PrivateAssets, Url
from core.logger import Logger
from core.parser.message import parser
from core.utils import init, init_async, load_prompt

PrivateAssets.set(os.path.abspath(os.path.dirname(__file__) + '/assets'))
init()
Url.disable_mm = True

count = 0


@client.event
async def on_ready():
    Logger.info('Logged on as ' + str(client.user))
    global count
    if count == 0:
        await init_async(FetchTarget)
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
                                        senderName=message.author.name, targetFrom=target, senderFrom="Discord|Client",
                                        clientName='Discord'),
                         session=Session(message=message, target=message.channel, sender=message.author))
    await parser(msg)


dc_token = Config('dc_token')
if dc_token:
    client.run(dc_token)
