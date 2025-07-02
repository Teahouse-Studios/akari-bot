import asyncio
import importlib
import logging
import os
import pkgutil
import re
import sys
import traceback

import discord

import bots.discord.slash as slash_modules

sys.path.append(os.getcwd())

from bots.discord.client import client  # noqa: E402
from bots.discord.context import DiscordContextManager, DiscordFetchedContextManager  # noqa: E402
from bots.discord.info import *  # noqa: E402
from core.builtins.bot import Bot  # noqa: E402
from core.builtins.session.info import SessionInfo  # noqa: E402
from core.builtins.message.chain import MessageChain  # noqa: E402
from core.builtins.utils import command_prefix  # noqa: E402
from core.config import Config  # noqa: E402
from core.constants.path import assets_path  # noqa: E402
from core.logger import Logger  # noqa: E402
from core.utils.info import Info  # noqa: E402
from core.client.init import client_init  # noqa: E402

dc_token = Config("discord_token", cfg_type=str, secret=True, table_name="bot_discord")


Bot.register_bot(client_name=client_name,
                 private_assets_path=os.path.join(assets_path, "private", "discord"))

ctx_id = Bot.register_context_manager(DiscordContextManager)
Bot.register_context_manager(DiscordFetchedContextManager, fetch_session=True)

count = 0


@client.event
async def on_ready():
    Logger.info(f"Logged on as {client.user}")
    global count
    if count == 0:
        await client_init(target_prefix_list, sender_prefix_list)
        count += 1
        logging.getLogger("discord").setLevel(logging.INFO)

slash_load_dir = os.path.abspath(
    os.path.join(os.path.abspath(os.path.dirname(__file__)), "slash")
)


def load_slashcommands():
    for subm in pkgutil.iter_modules(slash_modules.__path__):
        submodule_name = slash_modules.__name__ + "." + subm.name
        try:
            Logger.debug(f"Loading {submodule_name}...")
            importlib.import_module(submodule_name)
            Logger.debug(f"Successfully loaded {submodule_name}!")
        except Exception:
            Logger.exception(f"Failed to load {submodule_name}: {traceback.format_exc()}")


load_slashcommands()


@client.event
async def on_message(message: discord.Message):
    # don't respond to ourselves
    if message.author == client.user or message.author.bot:
        return
    target_from = target_channel_prefix
    if isinstance(message.channel, discord.DMChannel):
        target_from = target_dm_channel_prefix
    target_id = f"{target_from}|{message.channel.id}"
    sender_id = f"{sender_prefix}|{message.author.id}"

    reply_id = None
    if message.reference:
        reply_id = message.reference.message_id

    if match_at := re.match(r"^<@(.*?)>", message.content):  # pop up help information when user mentions bot
        if match_at.group(1) == str(client.user.id):
            message.content = re.sub(r"<@(.*?)>", "", message.content)
            if message.content in ["", " "]:
                message.content = f"{command_prefix[0]}help"
            else:
                message.content = f"{command_prefix[0]} {message.content}"
        else:
            return

    msg_chain = MessageChain.assign(re.sub(r"<@(.*?)>", rf"{sender_prefix}|\1", message.content))

    session = await SessionInfo.assign(target_id=target_id, sender_id=sender_id, sender_name=message.author.name,
                                       target_from=target_from, sender_from=sender_prefix, client_name=client_name, message_id=str(message.id),
                                       reply_id=reply_id, messages=msg_chain, ctx_slot=ctx_id)

    await Bot.process_message(session, message)


if Config("enable", False, table_name="bot_discord") or __name__ == "__main__":
    loop = asyncio.new_event_loop()
    Info.client_name = client_name
    if "subprocess" in sys.argv:
        Info.subprocess = True
    loop.run_until_complete(client.start(dc_token))
