import asyncio
import importlib
import logging
import os
import pkgutil
import re
import sys

import discord
import filetype

import bots.discord.slash as slash_modules
from bots.discord.client import discord_bot
from bots.discord.context import DiscordContextManager, DiscordFetchedContextManager
from bots.discord.info import *
from bots.discord.slash_context import DiscordSlashContextManager
from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import Plain, Image, Voice
from core.builtins.session.info import SessionInfo
from core.builtins.utils import command_prefix
from core.client.init import client_init
from core.config import Config
from core.constants.default import ignored_sender_default
from core.logger import Logger
from core.utils.http import download

Bot.register_bot(client_name=client_name)

ctx_id = Bot.register_context_manager(DiscordContextManager)
Bot.register_context_manager(DiscordFetchedContextManager, fetch_session=True)

dc_token = Config("discord_token", cfg_type=str, secret=True, table_name="bot_discord")
ignored_sender = Config("ignored_sender", ignored_sender_default)

count = 0


async def cleanup_typing_signal():
    while True:
        for f in DiscordContextManager.typing_flags:
            if f not in DiscordContextManager.context:
                DiscordContextManager.typing_flags[f].set()
        for fs in DiscordSlashContextManager.typing_flags:
            if fs not in DiscordSlashContextManager.context:
                DiscordSlashContextManager.typing_flags[fs].set()
        await asyncio.sleep(1)


@discord_bot.event
async def on_ready():
    Logger.info(f"Logged on as {discord_bot.user}")
    global count
    if count == 0:
        await client_init(target_prefix_list, sender_prefix_list)
        asyncio.create_task(cleanup_typing_signal())
        logging.getLogger("discord").setLevel(logging.INFO)
        count += 1


slash_load_dir = os.path.abspath(
    os.path.join(os.path.abspath(os.path.dirname(__file__)), "slash")
)


def load_slashcommands():
    for subm in pkgutil.iter_modules(slash_modules.__path__):
        if subm.name in ["context", "parser"]:  # dunno why these appear in the list in some environments
            continue
        submodule_name = slash_modules.__name__ + "." + subm.name
        try:
            Logger.debug(f"Loading {submodule_name}...")
            importlib.import_module(submodule_name)
            Logger.debug(f"Successfully loaded {submodule_name}!")
        except Exception:
            Logger.exception(f"Failed to load {submodule_name}: ")


load_slashcommands()


async def to_message_chain(message: discord.Message):
    lst = [Plain(re.sub(r"<@(.*?)>", rf"{sender_prefix}|\1", message.content))]
    for x in message.attachments:
        d = await download(x.url)
        if filetype.is_image(d):
            lst.append(Image(d))
        elif filetype.is_audio(d):
            lst.append(Voice(d))
    return MessageChain.assign(lst)


@discord_bot.event
async def on_message(message: discord.Message):
    # don't respond to ourselves
    if message.author == discord_bot.user or message.author.bot:
        return
    target_from = target_channel_prefix
    if isinstance(message.channel, discord.DMChannel):
        target_from = target_dm_channel_prefix
    target_id = f"{target_from}|{message.channel.id}"
    sender_id = f"{sender_prefix}|{message.author.id}"
    if sender_id in ignored_sender:
        return

    reply_id = None
    if message.reference:
        reply_id = message.reference.message_id

    if match_at := re.match(r"^<@(.*?)>", message.content):  # pop up help information when user mentions bot
        if match_at.group(1) == str(discord_bot.user.id):
            message.content = re.sub(r"<@(.*?)>", "", message.content).strip()
            if message.content in ["", " "]:
                message.content = f"{command_prefix[0]}help"
            else:
                message.content = f"{command_prefix[0]} {message.content}"
        else:
            return

    msg_chain = await to_message_chain(message)

    session = await SessionInfo.assign(target_id=target_id,
                                       sender_id=sender_id,
                                       sender_name=message.author.name,
                                       target_from=target_from,
                                       sender_from=sender_prefix,
                                       client_name=client_name,
                                       message_id=str(message.id),
                                       reply_id=reply_id,
                                       messages=msg_chain,
                                       ctx_slot=ctx_id
                                       )

    await Bot.process_message(session, message)


if Config("enable", False, table_name="bot_discord"):
    loop = asyncio.new_event_loop()
    discord_bot.run(dc_token)
