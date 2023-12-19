import importlib
import os
import re
import sys
import traceback

import discord

from bots.discord.client import client
from bots.discord.info import client_name
from bots.discord.message import MessageSession, FetchTarget
from config import Config
from core.builtins import PrivateAssets, Url
from core.logger import Logger
from core.parser.message import parser
from core.types import MsgInfo, Session
from core.utils.bot import init_async, load_prompt
from core.utils.info import Info

PrivateAssets.set(os.path.abspath(os.path.dirname(__file__) + '/assets'))
Url.disable_mm = True

count = 0

dc_token = Config('dc_token')


@client.event
async def on_ready():
    Logger.info('Logged on as ' + str(client.user))
    global count
    if count == 0:
        await init_async()
        await load_prompt(FetchTarget)
        count = 1


slash_load_dir = os.path.abspath(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'slash'))


def load_slashcommands():
    fun_file = None
    dir_list = os.listdir(slash_load_dir)
    for file_name in dir_list:
        try:
            file_path = os.path.join(slash_load_dir, file_name)
            fun_file = None
            if os.path.isdir(file_path):
                if file_name[0] != '_':
                    fun_file = file_name
            elif os.path.isfile(file_path):
                if file_name[0] != '_' and file_name.endswith('.py'):
                    fun_file = file_name[:-3]
            if fun_file:
                Logger.info(f'Loading slash.{fun_file}...')
                modules = 'bots.discord.slash.' + fun_file
                importlib.import_module(modules)
                Logger.info(f'Succeeded loaded bots.discord.slash.{fun_file}!')
        except BaseException:
            tb = traceback.format_exc()
            errmsg = f'Failed to load bots.discord.slash.{fun_file}: \n{tb}'
            Logger.error(errmsg)


load_slashcommands()


@client.event
async def on_message(message):
    # don't respond to ourselves
    if message.author == client.user or message.author.bot:
        return
    target = "Discord|Channel"
    if isinstance(message.channel, discord.DMChannel):
        target = "Discord|DM|Channel"
    target_id = f"{target}|{message.channel.id}"
    reply_id = None
    if message.reference:
        reply_id = message.reference.message_id
    prefix = None
    if match_at := re.match(r'^<@(.*?)>', message.content):
        if match_at.group(1) == str(client.user.id):
            prefix = ['']
            message.content = re.sub(r'<@(.*?)>', '', message.content)

    msg = MessageSession(
        target=MsgInfo(
            target_id=target_id,
            sender_id=f"Discord|Client|{message.author.id}",
            sender_name=message.author.name,
            target_from=target,
            sender_from="Discord|Client",
            client_name=client_name,
            message_id=message.id,
            reply_id=reply_id),
        session=Session(
            message=message,
            target=message.channel,
            sender=message.author))
    await parser(msg, prefix=prefix)


if 'subprocess' in sys.argv:
    Info.subprocess = True

client.run(dc_token)
