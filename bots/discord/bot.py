import asyncio
import importlib
import os
import re
import sys
import traceback

import discord

from bots.discord.client import client
from bots.discord.info import *
from core.builtins.bot import Bot
from core.builtins.session.info import SessionInfo
from core.builtins.message.chain import MessageChain
from core.builtins.utils import command_prefix
from core.config import Config
from core.constants.path import assets_path
from core.logger import Logger
from core.terminate import cleanup_sessions
from core.utils.info import Info
from core.client import client_init
import orjson as json

from bots.discord.context import DiscordContextManager, DiscordFetchedContextManager

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

slash_load_dir = os.path.abspath(
    os.path.join(os.path.abspath(os.path.dirname(__file__)), "slash")
)


def load_slashcommands():
    fun_file = None
    dir_list = []
    if not Info.binary_mode:
        dir_list = os.listdir(slash_load_dir)
    else:
        try:
            Logger.warning(
                "Binary mode detected, trying to load pre-built slash list..."
            )
            js = "assets/discord_slash_list.json"
            with open(js, "r", encoding="utf-8") as f:
                dir_list = json.loads(f.read())
        except Exception:
            Logger.error("Failed to load pre-built slash list, using default list.")
            dir_list = os.listdir(slash_load_dir)
    for file_name in dir_list:
        try:
            file_path = os.path.join(slash_load_dir, file_name)
            fun_file = None
            if not Info.binary_mode:
                if os.path.isdir(file_path):
                    if file_name[0] != "_":
                        fun_file = file_name
                elif os.path.isfile(file_path):
                    if file_name[0] != "_" and file_name.endswith(".py"):
                        fun_file = file_name[:-3]
            else:
                if file_name[0] != "_":
                    fun_file = file_name
                if file_name[0] != "_" and file_name.endswith(".py"):
                    fun_file = file_name[:-3]
            if fun_file:
                Logger.info(f"Loading slash.{fun_file}...")
                modules = "bots.discord.slash." + fun_file
                importlib.import_module(modules)
                Logger.success(f"Succeeded loaded bots.discord.slash.{fun_file}!")
        except Exception:
            tb = traceback.format_exc()
            errmsg = f"Failed to load bots.discord.slash.{fun_file}: \n{tb}"
            Logger.error(errmsg)


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


if Config("enable", False, table_name="bot_discord"):
    loop = asyncio.new_event_loop()
    try:
        Info.client_name = client_name
        if "subprocess" in sys.argv:
            Info.subprocess = True
        loop.run_until_complete(client.start(dc_token))
    except (KeyboardInterrupt, SystemExit):
        loop.run_until_complete(cleanup_sessions())
