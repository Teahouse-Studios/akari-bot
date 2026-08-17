import re

import botpy
from botpy.interaction import Interaction
from botpy.manage import GroupMemberEvent
from botpy.message import C2CMessage, DirectMessage, GroupMessage, Message

from bots.qqbot.context import QQBotContextManager, QQBotFetchedContextManager, cache_permission
from bots.qqbot.info import *
from bots.qqbot.features import group_disable_read_all_message_features, resolve_features, guild_features
from bots.qqbot.navigation import build_navigation
from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import Plain
from core.builtins.session.info import EventInfo, SessionInfo
from core.builtins.utils import command_prefix
from core.client.init import client_init
from bots.qqbot.config import QQBotConfig, QQBotSecretConfig
from core.config.base import CoreConfig
from core.constants.default import confirm_command_default
from core.logger import Logger

Bot.register_bot(client_name=client_name)
Logger.rename(client_name)
ctx_id = Bot.register_context_manager(QQBotContextManager)
Bot.register_context_manager(QQBotFetchedContextManager, fetch_session=True)

qqbot_appid = str(QQBotConfig.qq_bot_appid)
qqbot_openid = str(QQBotConfig.qq_bot_openid)
qqbot_secret = QQBotSecretConfig.qq_bot_secret
ignored_sender = CoreConfig.ignored_sender

initialized = False


class MyClient(botpy.Client):
    @staticmethod
    async def on_group_member_add(event: GroupMemberEvent):
        """将 QQ 官方机器人群成员加入事件转换为核心事件。"""
        member_openid = getattr(event, "member_openid", None) or getattr(event, "user_openid", None)
        group_openid = getattr(event, "group_openid", None)
        if not member_openid or not group_openid:
            Logger.warning(f"Incomplete QQBot group_member_add event: {event}")
            return
        Logger.debug(event)

        event_info = await EventInfo.assign(
            event_name="member_joined",
            target_id=f"{target_group_prefix}|{group_openid}",
            target_from=target_group_prefix,
            client_name=client_name,
            sender_id=f"{sender_prefix}|{member_openid}",
            sender_from=sender_prefix,
            data={"event_id": event.event_id, "timestamp": event.timestamp},
        )
        await Bot.process_event(event_info)

    @staticmethod
    async def on_group_member_remove(event: GroupMemberEvent):
        """将 QQ 官方机器人群成员退出事件转换为核心事件。"""
        member_openid = getattr(event, "member_openid", None) or getattr(event, "user_openid", None)
        group_openid = getattr(event, "group_openid", None)
        if not member_openid or not group_openid:
            Logger.warning(f"Incomplete QQBot group_member_remove event: {event}")
            return
        Logger.debug(event)

        event_info = await EventInfo.assign(
            event_name="member_left",
            target_id=f"{target_group_prefix}|{group_openid}",
            target_from=target_group_prefix,
            client_name=client_name,
            sender_id=f"{sender_prefix}|{member_openid}",
            sender_from=sender_prefix,
            data={"event_id": event.event_id, "timestamp": event.timestamp},
        )
        await Bot.process_event(event_info)

    async def on_ready(self):
        global initialized
        if not initialized:
            await client_init(target_prefix_list, sender_prefix_list, rename_logger=False)
            initialized = True
        QQBotFetchedContextManager.start_task_processor()

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
            bot_id=qqbot_openid,
        )

        await Bot.process_message(session, message, guild_features)

    @staticmethod
    async def on_message_create(message: Message):
        target_id = f"{target_guild_prefix}|{message.guild_id}|{message.channel_id}"
        sender_id = f"{sender_tiny_prefix}|{message.author.id}"
        if sender_id in ignored_sender:
            return

        reply_id = None
        if message.message_reference:
            reply_id = message.message_reference.message_id

        match_atme = False

        if qqbot_openid:
            if m := re.match(r"<@(.*?)>(.*)", message.content):
                if m.group(1) == qqbot_openid:
                    match_atme = True
                    message.content = m.group(2).strip()
                    if not message.content:
                        message.content = f"{command_prefix[0]}help"

        msg_chain = MessageChain.assign(re.sub(r"<@(.*?)>", rf"{sender_tiny_prefix}|\1", message.content))
        prefixes = [] if not match_atme else ["/"]

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
            prefixes=prefixes,
            bot_id=qqbot_openid,
            tmp={"message_type": "guild_direct"},
        )

        await Bot.process_message(session, message, guild_features)

    @staticmethod
    async def on_message_group_create(message: GroupMessage):
        Logger.debug(message)
        target_id = f"{target_group_prefix}|{message.group_openid}"
        sender_id = f"{sender_prefix}|{message.author.member_openid}"
        if sender_id in ignored_sender:
            return

        reply_id = None
        if message.mentions:
            reply_id = message.mentions[0].id

        match_atme = False

        if qqbot_openid:
            if m := re.match(r"<@(.*?)>(.*)", message.content):
                if m.group(1) == qqbot_openid:
                    match_atme = True
                    message.content = m.group(2).strip()
                    if not message.content:
                        message.content = f"{command_prefix[0]}help"
        msg_chain = MessageChain.assign(re.sub(r"<@(.*?)>", rf"{sender_prefix}|\1", message.content))
        prefixes = [] if not match_atme else ["/"]
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
            prefixes=prefixes,
            bot_id=qqbot_openid,
            tmp={"message_type": "group_direct"},
        )

        cache_permission(f"{target_id}|{sender_id}", message.author.member_role in ["admin", "owner"])

        await Bot.process_message(session, message, resolve_features(session))

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
            bot_id=qqbot_openid,
            tmp={"message_type": "group_at"},
        )

        cache_permission(f"{target_id}|{sender_id}", message.author.member_role in ["admin", "owner"])

        await Bot.process_message(session, message, resolve_features(session, group_disable_read_all_message_features))

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
            is_private=True,
            sender_from=sender_tiny_prefix,
            client_name=client_name,
            message_id=str(message.id),
            reply_id=reply_id,
            messages=msg_chain,
            ctx_slot=ctx_id,
            prefixes=["/"],
            bot_id=qqbot_openid,
        )

        await Bot.process_message(session, message, guild_features)

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
            is_private=True,
            sender_from=sender_prefix,
            client_name=client_name,
            message_id=str(message.id),
            reply_id=reply_id,
            messages=msg_chain,
            ctx_slot=ctx_id,
            prefixes=["/"],
            bot_id=qqbot_openid,
        )

        await Bot.process_message(session, message, resolve_features(session))

    @staticmethod
    async def on_interaction_create(interaction: Interaction):
        Logger.debug(interaction)
        await interaction.acknowledge()
        send_msg = interaction.data.resolved.button_data
        if not send_msg:
            Logger.warning(f"Unsupported QQBot interaction payload: {interaction}")
            return
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
            is_private=target_from in (target_c2c_prefix, target_direct_prefix),
            sender_from=sender_from,
            client_name=client_name,
            reply_id=interaction.data.resolved.message_id if quote_msg is None else quote_msg,
            messages=MessageChain.assign([Plain(send_msg)]),
            ctx_slot=ctx_id,
            bot_id=qqbot_openid,
        )
        await Bot.process_message(session, interaction, resolve_features(session))


intents = botpy.Intents.none()
intents.public_guild_messages = True
intents.public_messages = True
intents.direct_message = True
intents.interaction = True
intents.group_member_event = True
if QQBotConfig.qq_private_bot:
    intents.guild_messages = True

menu, panels = build_navigation()
client = MyClient(
    intents=intents,
    bot_log=None,
    loguru_logger=Logger.log,
    menu=menu,
    panels=panels,
    config_sync_strict=QQBotConfig.qq_navigation_sync_strict,
)
QQBotContextManager.client = client

if QQBotConfig.enable:
    client.run(appid=qqbot_appid, secret=qqbot_secret)
