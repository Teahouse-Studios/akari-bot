import asyncio
import re

import botpy
from botpy.interaction import Interaction
from botpy.message import C2CMessage, DirectMessage, GroupMessage, Message

from bots.qqbot.context import QQBotContextManager, QQBotFetchedContextManager
from bots.qqbot.info import *
from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import Plain
from core.builtins.session.info import SessionInfo
from core.builtins.utils import command_prefix
from core.client.init import client_init
from core.config import Config
from core.constants.default import ignored_sender_default, confirm_command_default
from core.logger import Logger

Bot.register_bot(client_name=client_name)
ctx_id = Bot.register_context_manager(QQBotContextManager)
Bot.register_context_manager(QQBotFetchedContextManager, fetch_session=True)

qqbot_appid = str(Config("qq_bot_appid", cfg_type=(int, str), table_name="bot_qqbot"))
qqbot_openid = str(Config("qq_bot_openid", default="", table_name="bot_qqbot"))
qqbot_secret = Config("qq_bot_secret", cfg_type=str, secret=True, table_name="bot_qqbot")
ignored_sender = Config("ignored_sender", ignored_sender_default)

initialized = False


class MyClient(botpy.Client):
    async def on_ready(self):
        global initialized
        if not initialized:
            await client_init(target_prefix_list, sender_prefix_list)
            asyncio.create_task(QQBotFetchedContextManager.process_tasks())
            initialized = True

    @staticmethod
    async def on_at_message_create(message: Message):
        target_id = f"{target_guild_prefix}|{message.guild_id}|{message.channel_id}"
        sender_id = f"{sender_tiny_prefix}|{message.author.id}"
        if sender_id in ignored_sender:
            return

        reply_id = None
        if message.message_reference:
            reply_id = message.message_reference.message_id

        message.content = re.sub(r"<@(.*?)>", "", message.content).strip()
        if not message.content:
            message.content = f"{command_prefix[0]}help"

        msg_chain = MessageChain.assign(re.sub(r"<@(.*?)>", rf"{sender_tiny_prefix}|\1", message.content))

        session = await SessionInfo.assign(
            target_id=target_id,
            sender_id=sender_id,
            sender_name=message.author.id[:6],
            target_from=target_guild_prefix,
            sender_from=sender_tiny_prefix,
            client_name=client_name,
            message_id=str(message.id),
            reply_id=reply_id,
            messages=msg_chain,
            ctx_slot=ctx_id,
            prefixes=["/"],
            tmp={"message_type": "guild_at"},
        )

        await Bot.process_message(session, message)

    @staticmethod
    async def on_message_create(message: Message):
        target_id = f"{target_guild_prefix}|{message.guild_id}|{message.channel_id}"
        sender_id = f"{sender_tiny_prefix}|{message.author.id}"
        if sender_id in ignored_sender:
            return

        reply_id = None
        if message.message_reference:
            reply_id = message.message_reference.message_id

        if qqbot_openid:
            message.content = re.sub(r"<@" + qqbot_openid + ">", "", message.content).strip()
        if not message.content.strip():
            message.content = f"{command_prefix[0]}help"

        msg_chain = MessageChain.assign(re.sub(r"<@(.*?)>", rf"{sender_tiny_prefix}|\1", message.content))

        session = await SessionInfo.assign(
            target_id=target_id,
            sender_id=sender_id,
            sender_name=message.author.username,
            target_from=target_guild_prefix,
            sender_from=sender_tiny_prefix,
            client_name=client_name,
            message_id=str(message.id),
            reply_id=reply_id,
            messages=msg_chain,
            ctx_slot=ctx_id,
            prefixes=["/"],
            tmp={"message_type": "guild_direct"},
        )

        await Bot.process_message(session, message)

    @staticmethod
    async def on_message_group_create(message: GroupMessage):
        Logger.debug(message)
        target_id = f"{target_group_prefix}|{message.group_openid}"
        sender_id = f"{sender_prefix}|{message.author.member_openid}"
        if sender_id in ignored_sender:
            return

        reply_id = None
        if message.message_reference:
            reply_id = message.message_reference.message_id

        if qqbot_openid:
            message.content = re.sub(r"<@" + qqbot_openid + ">", "", message.content).strip()
        msg_chain = MessageChain.assign(message.content)

        session = await SessionInfo.assign(
            target_id=target_id,
            sender_id=sender_id,
            sender_name=message.author.username,
            target_from=target_group_prefix,
            sender_from=sender_prefix,
            client_name=client_name,
            message_id=str(message.id),
            reply_id=reply_id,
            messages=msg_chain,
            ctx_slot=ctx_id,
            prefixes=["/"],
            tmp={"message_type": "group_direct"},
        )

        await Bot.process_message(session, message)

    @staticmethod
    async def on_group_at_message_create(message: GroupMessage):

        target_id = f"{target_group_prefix}|{message.group_openid}"
        sender_id = f"{sender_prefix}|{message.author.member_openid}"
        if sender_id in ignored_sender:
            return

        reply_id = None
        if message.message_reference:
            reply_id = message.message_reference.message_id

        message.content = re.sub(r"<@(.*?)>", "", message.content).strip()
        if not message.content:
            message.content = f"{command_prefix[0]}help"

        msg_chain = MessageChain.assign(re.sub(r"<@(.*?)>", rf"{sender_prefix}|\1", message.content))

        session = await SessionInfo.assign(
            target_id=target_id,
            sender_id=sender_id,
            sender_name=message.author.username,
            target_from=target_group_prefix,
            sender_from=sender_prefix,
            client_name=client_name,
            message_id=str(message.id),
            reply_id=reply_id,
            messages=msg_chain,
            ctx_slot=ctx_id,
            prefixes=["/"],
            tmp={"message_type": "group_at"},
        )

        await Bot.process_message(session, message)

    @staticmethod
    async def on_direct_message_create(message: DirectMessage):

        target_id = f"{target_direct_prefix}|{message.guild_id}"
        sender_id = f"{sender_tiny_prefix}|{message.author.id}"
        if sender_id in ignored_sender:
            return

        reply_id = None
        if message.message_reference:
            reply_id = message.message_reference.message_id

        msg_chain = MessageChain.assign(message.content)

        session = await SessionInfo.assign(
            target_id=target_id,
            sender_id=sender_id,
            sender_name=message.author.username,
            target_from=target_direct_prefix,
            sender_from=sender_tiny_prefix,
            client_name=client_name,
            message_id=str(message.id),
            reply_id=reply_id,
            messages=msg_chain,
            ctx_slot=ctx_id,
            prefixes=["/"],
        )

        await Bot.process_message(session, message)

    @staticmethod
    async def on_c2c_message_create(message: C2CMessage):
        target_id = f"{target_c2c_prefix}|{message.author.user_openid}"
        sender_id = f"{sender_prefix}|{message.author.user_openid}"
        if sender_id in ignored_sender:
            return

        reply_id = None
        if message.message_reference:
            reply_id = message.message_reference.message_id

        msg_chain = MessageChain.assign(message.content)

        session = await SessionInfo.assign(
            target_id=target_id,
            sender_id=sender_id,
            sender_name=message.author.user_openid[:6],
            target_from=target_c2c_prefix,
            sender_from=sender_prefix,
            client_name=client_name,
            message_id=str(message.id),
            reply_id=reply_id,
            messages=msg_chain,
            ctx_slot=ctx_id,
            prefixes=["/"],
        )

        await Bot.process_message(session, message)

    @staticmethod
    async def on_interaction_create(interaction: Interaction):
        Logger.debug(interaction)
        await client.api.on_interaction_result(interaction.id, 0)
        if interaction.chat_type == 0:
            target_id = f"{target_guild_prefix}|{interaction.guild_id}|{interaction.channel_id}"
            sender_id = f"{sender_tiny_prefix}|{interaction.user_openid}"
            target_from = target_guild_prefix
            sender_from = sender_tiny_prefix
        elif interaction.chat_type == 1:
            target_id = f"{target_group_prefix}|{interaction.group_openid}"
            sender_id = f"{sender_prefix}|{interaction.group_member_openid}"
            target_from = target_group_prefix
            sender_from = sender_prefix
        elif interaction.chat_type == 2:
            target_id = f"{target_c2c_prefix}|{interaction.user_openid}"
            sender_id = f"{sender_prefix}|{interaction.user_openid}"
            target_from = target_c2c_prefix
            sender_from = sender_prefix
        else:
            Logger.warning(f"Unknown interactions: {interaction}")
            return
        if sender_id in ignored_sender:
            return
        send_msg = interaction.data.resolved.button_data
        quote_msg = None
        match_quote = re.match(r"<q:(.*?)>(.*)", send_msg)

        if match_quote:
            quote_msg = match_quote.group(1)
            send_msg = match_quote.group(2)
        if send_msg == "confirm_yes":
            send_msg = confirm_command_default[0]
        elif send_msg == "confirm_no":
            send_msg = "no"

        session = await SessionInfo.assign(
            target_id=target_id,
            sender_id=sender_id,
            target_from=target_from,
            sender_from=sender_from,
            client_name=client_name,
            reply_id=interaction.data.resolved.message_id if quote_msg is None else quote_msg,
            messages=MessageChain.assign([Plain(send_msg)]),
            ctx_slot=ctx_id,
        )
        await Bot.process_message(session, interaction)


intents = botpy.Intents.none()
intents.public_guild_messages = True
intents.public_messages = True
intents.direct_message = True
intents.interaction = True
if Config("qq_private_bot", False, table_name="bot_qqbot"):
    intents.guild_messages = True

client = MyClient(intents=intents, bot_log=None)

if Config("enable", False, table_name="bot_qqbot"):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(client.start(appid=qqbot_appid, secret=qqbot_secret))
