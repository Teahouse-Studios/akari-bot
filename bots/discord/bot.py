import os
import re

import discord

from bots.discord.client import client
from bots.discord.message import MessageSession, FetchTarget
from config import Config
from core.elements import MsgInfo, Session, PrivateAssets, Url
from core.logger import Logger
from core.parser.message import parser
from core.utils import init, init_async, load_prompt, MessageTaskManager
from core.loader import ModulesManager


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


"""modules = [x for x in ModulesManager.return_modules_list_as_dict()]
for module in modules:
    name = re.sub(r'\W*', '', module)
    @client.slash_command(guild_ids=[557879624575614986], name=name)  # Create a slash command
    async def hello(ctx: discord.ApplicationContext):
        await ctx.respond(f"Hello {ctx.author}!")"""


@client.event
async def on_message(message):
    # don't respond to ourselves
    if message.author == client.user:
        return
    target = "Discord|Channel"
    if isinstance(message.channel, discord.DMChannel):
        target = "Discord|DM|Channel"
    targetId = f"{target}|{message.channel.id}"
    replyId = None
    if message.reference is not None:
        replyId = message.reference.message_id
    prefix = None
    if match_at := re.match(r'^<@(.*?)>', message.content):
        if match_at.group(1) == str(client.user.id):
            prefix = ['']
            message.content = re.sub(r'<@(.*?)>', '', message.content)

    msg = MessageSession(target=MsgInfo(targetId=targetId,
                                        senderId=f"Discord|Client|{message.author.id}",
                                        senderName=message.author.name, targetFrom=target, senderFrom="Discord|Client",
                                        clientName='Discord',
                                        messageId=message.id,
                                        replyId=replyId),
                         session=Session(message=message, target=message.channel, sender=message.author))
    MessageTaskManager.check(msg)
    await parser(msg, prefix=prefix)


dc_token = Config('dc_token')
if dc_token:
    client.run(dc_token)
