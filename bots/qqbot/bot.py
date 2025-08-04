import asyncio
import re

import botpy
from botpy.message import C2CMessage, DirectMessage, GroupMessage, Message

from bots.qqbot.context import QQBotContextManager
from bots.qqbot.info import *
from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.session.info import SessionInfo
from core.builtins.utils import command_prefix
from core.client.init import client_init
from core.config import Config
from core.constants.default import ignored_sender_default

Bot.register_bot(client_name=client_name)
ctx_id = Bot.register_context_manager(QQBotContextManager)

qqbot_appid = str(Config("qq_bot_appid", cfg_type=(int, str), table_name="bot_qqbot"))
qqbot_secret = Config("qq_bot_secret", cfg_type=str, secret=True, table_name="bot_qqbot")
ignored_sender = Config("ignored_sender", ignored_sender_default)
dirty_word_check = Config("enable_dirty_check", False)
use_url_manager = Config("enable_urlmanager", False)


class MyClient(botpy.Client):
    async def on_ready(self):
        await client_init(target_prefix_list, sender_prefix_list)

    @staticmethod
    async def on_at_message_create(message: Message):
        prefixes = None
        require_enable_modules = True

        target_id = f"{target_guild_prefix}|{message.guild_id}|{message.channel_id}"
        sender_id = f"{sender_tiny_prefix}|{message.author.id}"
        if sender_id in ignored_sender:
            return

        reply_id = None
        if message.message_reference:
            reply_id = message.message_reference.message_id

        message.content = re.sub(r"<@(.*?)>", "", message.content).strip()
        if message.content in ["", " "]:
            message.content = f"{command_prefix[0]}help"

        if message.content.strip().startswith("/"):
            prefixes = ["/"]
            require_enable_modules = False

        msg_chain = MessageChain.assign(re.sub(r"<@(.*?)>", rf"{sender_tiny_prefix}|\1", message.content))

        session = await SessionInfo.assign(target_id=target_id,
                                           sender_id=sender_id,
                                           sender_name=message.author.id[:6],
                                           target_from=target_guild_prefix,
                                           sender_from=sender_tiny_prefix,
                                           client_name=client_name,
                                           message_id=str(message.id),
                                           reply_id=reply_id,
                                           messages=msg_chain,
                                           ctx_slot=ctx_id,
                                           prefixes=prefixes,
                                           require_enable_modules=require_enable_modules,
                                           require_check_dirty_words=dirty_word_check,
                                           use_url_manager=use_url_manager,
                                           force_use_url_manager=True
                                           )

        await Bot.process_message(session, message)

    @staticmethod
    async def on_message_create(message: Message):
        prefixes = None
        require_enable_modules = True

        target_id = f"{target_guild_prefix}|{message.guild_id}|{message.channel_id}"
        sender_id = f"{sender_tiny_prefix}|{message.author.id}"
        if sender_id in ignored_sender:
            return

        reply_id = None
        if message.message_reference:
            reply_id = message.message_reference.message_id

        if message.content in ["", " "]:
            message.content = f"{command_prefix[0]}help"

        if message.content.strip().startswith("/"):
            prefixes = ["/"]
            require_enable_modules = False

        msg_chain = MessageChain.assign(re.sub(r"<@(.*?)>", rf"{sender_tiny_prefix}|\1", message.content))

        session = await SessionInfo.assign(target_id=target_id,
                                           sender_id=sender_id,
                                           sender_name=message.author.id[:6],
                                           target_from=target_guild_prefix,
                                           sender_from=sender_tiny_prefix,
                                           client_name=client_name,
                                           message_id=str(message.id),
                                           reply_id=reply_id,
                                           messages=msg_chain,
                                           ctx_slot=ctx_id,
                                           prefixes=prefixes,
                                           require_enable_modules=require_enable_modules,
                                           require_check_dirty_words=dirty_word_check,
                                           use_url_manager=use_url_manager,
                                           force_use_url_manager=True
                                           )

        await Bot.process_message(session, message)

    @staticmethod
    async def on_group_at_message_create(message: GroupMessage):
        prefixes = None
        require_enable_modules = True

        target_id = f"{target_group_prefix}|{message.group_openid}"
        sender_id = f"{sender_prefix}|{message.author.member_openid}"
        if sender_id in ignored_sender:
            return

        reply_id = None
        if message.message_reference:
            reply_id = message.message_reference.message_id

        message.content = re.sub(r"<@(.*?)>", "", message.content).strip()
        if message.content in ["", " "]:
            message.content = f"{command_prefix[0]}help"

        if message.content.strip().startswith("/"):
            prefixes = ["/"]
            require_enable_modules = False

        msg_chain = MessageChain.assign(re.sub(r"<@(.*?)>", rf"{sender_prefix}|\1", message.content))

        session = await SessionInfo.assign(target_id=target_id,
                                           sender_id=sender_id,
                                           sender_name=message.author.member_openid[:6],
                                           target_from=target_group_prefix,
                                           sender_from=sender_prefix,
                                           client_name=client_name,
                                           message_id=str(message.id),
                                           reply_id=reply_id,
                                           messages=msg_chain,
                                           ctx_slot=ctx_id,
                                           prefixes=prefixes,
                                           require_enable_modules=require_enable_modules,
                                           require_check_dirty_words=dirty_word_check,
                                           use_url_manager=use_url_manager,
                                           force_use_url_manager=True
                                           )

        await Bot.process_message(session, message)

    @staticmethod
    async def on_direct_message_create(message: DirectMessage):
        prefixes = None
        require_enable_modules = True

        target_id = f"{target_direct_prefix}|{message.guild_id}"
        sender_id = f"{sender_tiny_prefix}|{message.author.id}"
        if sender_id in ignored_sender:
            return

        reply_id = None
        if message.message_reference:
            reply_id = message.message_reference.message_id

        if message.content.strip().startswith("/"):
            prefixes = ["/"]
            require_enable_modules = False

        msg_chain = MessageChain.assign(message.content)

        session = await SessionInfo.assign(target_id=target_id,
                                           sender_id=sender_id,
                                           sender_name=message.author.id[:6],
                                           target_from=target_direct_prefix,
                                           sender_from=sender_tiny_prefix,
                                           client_name=client_name,
                                           message_id=str(message.id),
                                           reply_id=reply_id,
                                           messages=msg_chain,
                                           ctx_slot=ctx_id,
                                           prefixes=prefixes,
                                           require_enable_modules=require_enable_modules,
                                           require_check_dirty_words=dirty_word_check,
                                           use_url_manager=use_url_manager,
                                           force_use_url_manager=True
                                           )

        await Bot.process_message(session, message)

    @staticmethod
    async def on_c2c_message_create(message: C2CMessage):
        prefixes = None
        require_enable_modules = True

        target_id = f"{target_c2c_prefix}|{message.author.user_openid}"
        sender_id = f"{sender_prefix}|{message.author.user_openid}"
        if sender_id in ignored_sender:
            return

        reply_id = None
        if message.message_reference:
            reply_id = message.message_reference.message_id

        if message.content.strip().startswith("/"):
            prefixes = ["/"]
            require_enable_modules = False

        msg_chain = MessageChain.assign(message.content)

        session = await SessionInfo.assign(target_id=target_id,
                                           sender_id=sender_id,
                                           sender_name=message.author.user_openid[:6],
                                           target_from=target_c2c_prefix,
                                           sender_from=sender_prefix,
                                           client_name=client_name,
                                           message_id=str(message.id),
                                           reply_id=reply_id,
                                           messages=msg_chain,
                                           ctx_slot=ctx_id,
                                           prefixes=prefixes,
                                           require_enable_modules=require_enable_modules,
                                           require_check_dirty_words=dirty_word_check,
                                           use_url_manager=use_url_manager,
                                           force_use_url_manager=True
                                           )

        await Bot.process_message(session, message)


intents = botpy.Intents.none()
intents.public_guild_messages = True
intents.public_messages = True
intents.direct_message = True
if Config("qq_private_bot", False, table_name="bot_qqbot"):
    intents.guild_messages = True

client = MyClient(intents=intents, bot_log=None)

if Config("enable", False, table_name="bot_qqbot"):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(client.start(appid=qqbot_appid, secret=qqbot_secret))
