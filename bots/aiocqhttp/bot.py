import html
import logging
import os
import re
import sys

import orjson as json
from aiocqhttp import Event
from hypercorn import Config as HyperConfig

from bots.aiocqhttp.client import bot
from bots.aiocqhttp.info import *
from bots.aiocqhttp.message import MessageSession, FetchTarget
from core.bot_init import load_prompt, init_async
from core.builtins import PrivateAssets
from core.builtins.utils import command_prefix
from core.builtins.temp import Temp
from core.close import cleanup_sessions
from core.config import Config
from core.constants.default import issue_url_default, ignored_sender_default, qq_host_default
from core.constants.info import Info
from core.constants.path import assets_path
from core.database.models import SenderInfo, TargetInfo, UnfriendlyActionRecords
from core.i18n import Locale
from core.parser.message import parser
from core.tos import tos_report
from core.types import MsgInfo, Session


PrivateAssets.set(os.path.join(assets_path, "private", "aiocqhttp"))
Info.dirty_word_check = Config("enable_dirty_check", False)
Info.use_url_manager = Config("enable_urlmanager", False)
enable_listening_self_message = Config("qq_enable_listening_self_message", False, table_name="bot_aiocqhttp")
enable_tos = Config("enable_tos", True)
ignored_sender = Config("ignored_sender", ignored_sender_default)
default_locale = Config("default_locale", cfg_type=str)


@bot.on_startup
async def startup():
    await init_async()
    bot.logger.setLevel(logging.WARNING)


@bot.on_websocket_connection
async def _(event: Event):
    await load_prompt(FetchTarget)
    qq_login_info = await bot.call_action("get_login_info")
    qq_account = qq_login_info.get("user_id")
    Temp().data["qq_account"] = qq_account
    Temp().data["qq_nickname"] = qq_login_info.get("nickname")


async def message_handler(event: Event):
    qq_account = Temp().data.get("qq_account")
    if event.detail_type == "private" and event.sub_type == "group" \
            and Config("qq_disable_temp_session", True, table_name="bot_aiocqhttp"):
        return

    if event.detail_type == "group":
        target_id = f"{target_group_prefix}|{event.group_id}"
    else:
        target_id = f"{target_private_prefix}|{event.user_id}"
    sender_id = f"{sender_prefix}|{event.user_id}"

    if sender_id in ignored_sender:
        return
    string_post = False
    if isinstance(event.message, str):
        string_post = True

    if string_post:
        match_json = re.match(r"\[CQ:json,data=(.*?)\]", event.message, re.MULTILINE | re.DOTALL)
        if match_json:
            load_json = json.loads(html.unescape(match_json.group(1)))
            if load_json["app"] == "com.tencent.multimsg":
                event.message = f"[CQ:forward,id={load_json["meta"]["detail"]["resid"]}]"
    else:
        if event.message[0]["type"] == "json":
            load_json = json.loads(event.message[0]["data"]["data"])
            if load_json["app"] == "com.tencent.multimsg":
                event.message = [{"type": "forward", "data": {"id": f"{load_json["meta"]["detail"]["resid"]}"}}]

    reply_id = None
    if string_post:
        match_reply = re.match(r"^\[CQ:reply,id=(-?\d+).*\].*", event.message)
        if match_reply:
            reply_id = int(match_reply.group(1))
    else:
        if event.message[0]["type"] == "reply":
            reply_id = int(event.message[0]["data"]["id"])

    prefix = None
    if string_post:
        if match_at := re.match(r"^\[CQ:at,qq=(\d+).*\](.*)", event.message):
            if match_at.group(1) == str(qq_account):
                event.message = match_at.group(2)
                if event.message in ["", " "]:
                    event.message = f"{command_prefix[0]}help"
                    prefix = command_prefix
            else:
                return
    else:
        if event.message[0]["type"] == "at":
            if event.message[0]["data"]["qq"] == str(qq_account):
                event.message = event.message[1:]
                if not event.message or \
                        event.message[0]["type"] == "text" and event.message[0]["data"]["text"] == " ":
                    event.message = [{"type": "text", "data": {"text": f"{command_prefix[0]}help"}}]
                    prefix = command_prefix
            else:
                return

    msg = MessageSession(
        MsgInfo(
            target_id=target_id,
            sender_id=sender_id,
            target_from=target_group_prefix if event.detail_type == "group" else target_private_prefix,
            sender_from=sender_prefix,
            sender_name=event.sender["nickname"],
            client_name=client_name,
            message_id=event.message_id,
            reply_id=reply_id),
        Session(
            message=event,
            target=event.group_id if event.detail_type == "group" else event.user_id,
            sender=event.user_id))
    await parser(msg, running_mention=True, prefix=prefix)


if enable_listening_self_message:
    @bot.on("message_sent")
    async def _(event: Event):
        await message_handler(event)


@bot.on_message("group", "private")
async def _(event: Event):
    await message_handler(event)


class GuildAccountInfo:
    tiny_id = None


@bot.on_message("guild")
async def _(event):
    if not GuildAccountInfo.tiny_id:
        profile = await bot.call_action("get_guild_service_profile")
        GuildAccountInfo.tiny_id = profile["tiny_id"]
    target_id = f"{target_guild_prefix}|{event.guild_id}|{event.channel_id}"
    sender_id = f"{sender_tiny_prefix}|{event.user_id}"
    if sender_id in ignored_sender:
        return
    if event.user_id == GuildAccountInfo.tiny_id:
        return
    reply_id = None
    match_reply = re.match(r"^\[CQ:reply,id=(-?\d+).*\].*", event.message)
    if match_reply:
        reply_id = int(match_reply.group(1))
    msg = MessageSession(MsgInfo(target_id=target_id,
                                 sender_id=sender_id,
                                 target_from=target_guild_prefix,
                                 sender_from=sender_tiny_prefix,
                                 sender_name=event.sender["nickname"],
                                 client_name=client_name,
                                 message_id=event.message_id,
                                 reply_id=reply_id),
                         Session(message=event,
                                 target=f"{event.guild_id}|{event.channel_id}",
                                 sender=event.user_id))
    await parser(msg, running_mention=True)


@bot.on("request.friend")
async def _(event: Event):
    sender_id = f"{sender_prefix}|{event.user_id}"
    sender_info = await SenderInfo.get(sender_id=sender_id)
    if sender_info.superuser or sender_info.trusted:
        return {"approve": True}
    if Config("qq_allow_approve_friend", False, table_name="bot_aiocqhttp"):
        if sender_info.blocked:
            return {"approve": False}
        return {"approve": True}


@bot.on("request.group.invite")
async def _(event: Event):
    sender_id = f"{sender_prefix}|{event.user_id}"
    sender_info = await SenderInfo.get(sender_id=sender_id)
    target_id = f"{target_group_prefix}|{event.group_id}"
    target_info = await TargetInfo.get(target_id=target_id)
    if sender_info.superuser or sender_info.trusted:
        return {"approve": True}
    if Config("qq_allow_approve_group_invite", False, table_name="bot_aiocqhttp"):
        if target_info.blocked:
            return {"approve": False}
        return {"approve": True}


@bot.on_notice("group_ban")
async def _(event: Event):
    qq_account = Temp().data.get("qq_account")
    if enable_tos and event.user_id == int(qq_account):
        sender_id = f"{sender_prefix}|{event.operator_id}"
        sender_info = await SenderInfo.get(sender_id=sender_id)
        target_id = f"{target_group_prefix}|{event.group_id}"
        target_info = await TargetInfo.get(target_id=target_id)
        await UnfriendlyActionRecords.create(target_id=event.group_id,
                                             sender_id=event.operator_id,
                                             action="mute",
                                             detail=str(event.duration))
        result = await UnfriendlyActionRecords.check_mute(target_id=event.group_id)
        if event.duration >= 259200:  # 3 days
            result = True
        if result and not sender_info.superuser:
            reason = Locale(default_locale).t("tos.message.reason.mute")
            await tos_report(sender_id, target_id, reason, banned=True)
            await target_info.edit_attr("blocked", True)
            await bot.call_action("set_group_leave", group_id=event.group_id)
            await sender_info.switch_identity(trust=False)
            await bot.call_action("delete_friend", friend_id=event.operator_id)


@bot.on_notice("group_decrease")
async def _(event: Event):
    if enable_tos and event.sub_type == "kick_me":
        sender_id = f"{sender_prefix}|{event.operator_id}"
        sender_info = await SenderInfo.get(sender_id=sender_id)
        target_id = f"{target_group_prefix}|{event.group_id}"
        target_info = await TargetInfo.get(target_id=target_id)
        await UnfriendlyActionRecords.create(target_id=event.group_id,
                                             sender_id=event.operator_id,
                                             action="kick")
        if not sender_info.superuser:
            reason = Locale(default_locale).t("tos.message.reason.kick")
            await tos_report(sender_id, target_id, reason, banned=True)
            await target_info.edit_attr("blocked", True)
            await sender_info.switch_identity(trust=False)
            await bot.call_action("delete_friend", friend_id=event.operator_id)


@bot.on_message("group")
async def _(event: Event):
    if enable_tos:
        target_id = f"{target_group_prefix}|{event.group_id}"
        target_info = await TargetInfo.get_or_none(target_id=target_id)
        if target_info and target_info.blocked:
            res = Locale(default_locale).t("tos.message.in_group_blocklist")
            if issue_url := Config("issue_url", issue_url_default):
                res += "\n" + Locale(default_locale).t("tos.message.appeal", issue_url=issue_url)
            await bot.send(event=event, message=res)
            await bot.call_action("set_group_leave", group_id=event.group_id)


@bot.server_app.after_serving
async def _():
    await cleanup_sessions()


qq_host = Config("qq_host", default=qq_host_default, table_name="bot_aiocqhttp")
if qq_host and Config("enable", False, table_name="bot_aiocqhttp"):
    argv = sys.argv
    Info.client_name = client_name
    HyperConfig.startup_timeout = 120
    if "subprocess" in sys.argv:
        Info.subprocess = True
    host, port = qq_host.split(":")
    bot.run(host=host, port=port, debug=False)
