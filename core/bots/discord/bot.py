import asyncio

from core.bots.discord.client import client

from core.elements import MsgInfo, MessageSession, Session
from core.template import Template
from core.bots.discord.template import Template as BotTemplate
from core.logger import Logger
from core.parser.message import parser
from config import Config
from core.elements import MessageSession

Template.bind_template(BotTemplate)


@client.event
async def on_ready():
    Logger.info('Logged on as ' + str(client.user))


@client.event
async def on_message(message):
    # don't respond to ourselves
    if message.author == client.user:
        return
    msg = MessageSession(target=MsgInfo(targetId=message.channel.id, senderId=message.author.id,
                                        senderName=message.author.name, msgFrom='Discord'),
                         session=Session(message=message, target=message.channel, sender=message.author))
    await parser(msg)


dc_token = Config('dc_token')
if dc_token:
    client.run(dc_token)
