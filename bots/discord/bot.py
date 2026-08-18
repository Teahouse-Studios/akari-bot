import importlib
import logging
import pkgutil
import re
from pathlib import Path

import discord
import filetype

import bots.discord.slash as slash_modules
from bots.discord.client import discord_bot, ensure_client_initialized
from bots.discord.buttons import set_action_text_submit_handler, set_button_click_handler
from bots.discord.interactions import handle_action_text_submit, handle_button_click
from bots.discord.context import DiscordContextManager, DiscordFetchedContextManager
from bots.discord.events import guild_member_joined, guild_member_left
from bots.discord.info import *
from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import Plain, Image, Voice
from core.builtins.session.info import SessionInfo
from core.builtins.utils import command_prefix
from bots.discord.config import DiscordConfig, DiscordSecretConfig
from core.config.base import CoreConfig
from core.logger import Logger
from core.utils.http import download

Bot.register_bot(client_name=client_name)

ctx_id = Bot.register_context_manager(DiscordContextManager)
Bot.register_context_manager(DiscordFetchedContextManager, fetch_session=True)
set_button_click_handler(lambda interaction, button: handle_button_click(interaction, button, ctx_id))
set_action_text_submit_handler(
    lambda interaction, command, reference, origin_message: handle_action_text_submit(
        interaction,
        command,
        reference,
        origin_message,
        ctx_id,
    )
)

dc_token = DiscordSecretConfig.discord_token
ignored_sender = CoreConfig.ignored_sender
mention_required = CoreConfig.mention_required


count = 0


@discord_bot.event
async def on_ready():
    Logger.info(f"Logged on as {discord_bot.user}")
    global count
    if count == 0:
        await ensure_client_initialized()
        logging.getLogger("discord").setLevel(logging.INFO)
        count += 1


slash_load_dir = (Path(__file__).parent / "slash").resolve()


def load_slashcommands():
    for subm in pkgutil.iter_modules(slash_modules.__path__):
        if subm.name in ["context", "parser"]:  # dunno why these appear in the list in some environments
            continue
        module_py_name = f"{slash_modules.__name__}.{subm.name}"
        try:
            Logger.debug(f"Loading {module_py_name}...")
            importlib.import_module(module_py_name)
            Logger.debug(f"Successfully loaded {module_py_name}!")
        except Exception:
            Logger.exception(f"Failed to load {module_py_name}: ")


load_slashcommands()


@discord_bot.event
async def on_member_join(member: discord.Member):
    """接收 Discord 服务器成员加入事件。"""
    sender_id = f"{sender_prefix}|{member.id}"
    if member.id == discord_bot.user.id or sender_id in ignored_sender:
        return

    await ensure_client_initialized()
    await guild_member_joined(member.id, member.guild.id, member.joined_at)


@discord_bot.event
async def on_member_remove(member: discord.Member):
    """接收 Discord 服务器成员离开事件。"""
    sender_id = f"{sender_prefix}|{member.id}"
    if member.id == discord_bot.user.id or sender_id in ignored_sender:
        return

    await ensure_client_initialized()
    await guild_member_left(member.id, member.guild.id)


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

    at_message = False
    if match_at := re.match(r"^<@(.*?)>", message.content):
        if match_at.group(1) == str(discord_bot.user.id):
            at_message = True
            message.content = re.sub(r"<@(.*?)>", "", message.content).strip()
            if not message.content:
                message.content = f"{command_prefix[0]}help"
        else:
            return
    if mention_required and not at_message and not isinstance(message.channel, discord.DMChannel):
        return

    msg_chain = await to_message_chain(message)

    await ensure_client_initialized()
    session = await SessionInfo.assign(
        target_id=target_id,
        sender_id=sender_id,
        sender_name=message.author.name,
        target_from=target_from,
        is_private=target_from == target_dm_channel_prefix,
        sender_from=sender_prefix,
        client_name=client_name,
        message_id=str(message.id),
        reply_id=str(reply_id),
        messages=msg_chain,
        ctx_slot=ctx_id,
        bot_id=discord_bot.user.id,
    )

    await Bot.process_message(session, message)


@discord_bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if payload.user_id == discord_bot.user.id:
        return
    Logger.debug(payload)
    sender_id = f"{sender_prefix}|{payload.user_id}"
    if sender_id in ignored_sender:
        return
    target_from = target_channel_prefix
    if isinstance(await discord_bot.fetch_channel(payload.channel_id), discord.DMChannel):
        target_from = target_dm_channel_prefix
    target_id = f"{target_from}|{payload.channel_id}"
    await ensure_client_initialized()
    session = await SessionInfo.assign(
        target_id=target_id,
        sender_id=sender_id,
        target_from=target_from,
        is_private=target_from == target_dm_channel_prefix,
        sender_from=sender_prefix,
        client_name=client_name,
        reply_id=str(payload.message_id),
        messages=MessageChain.assign([Plain(payload.emoji.name)]),
        ctx_slot=ctx_id,
        bot_id=discord_bot.user.id,
    )
    await Bot.process_message(session, payload)


if DiscordConfig.enable:
    discord_bot.run(dc_token)
