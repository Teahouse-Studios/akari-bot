import asyncio
import html
import logging
import re

import emoji
import orjson
from aiocqhttp import Event
from hypercorn import Config as HyperConfig

from bots.aiocqhttp.client import aiocqhttp_bot
from bots.aiocqhttp.context import AIOCQContextManager, AIOCQFetchedContextManager
from bots.aiocqhttp.info import *
from bots.aiocqhttp.utils import to_message_chain, get_onebot_implementation
from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import Plain
from core.builtins.session.info import SessionInfo
from core.builtins.temp import Temp
from core.builtins.utils import command_prefix
from core.client.init import client_init
from core.config import Config
from core.constants.default import confirm_command_default, issue_url_default, ignored_sender_default, qq_host_default
from core.database.models import SenderInfo, TargetInfo, UnfriendlyActionRecords
from core.i18n import Locale
from core.logger import Logger
from core.tos import tos_report

Bot.register_bot(client_name=client_name)
ctx_id = Bot.register_context_manager(AIOCQContextManager)
Bot.register_context_manager(AIOCQFetchedContextManager, fetch_session=True)

dirty_word_check = Config("enable_dirty_check", False)
default_locale = Config("default_locale", cfg_type=str)
ignored_sender = Config("ignored_sender", ignored_sender_default)
enable_tos = Config("enable_tos", True)
mention_required = Config("mention_required", False)
quick_confirm = Config("quick_confirm", True)
use_url_manager = Config("enable_urlmanager", False)
disable_temp_session = Config("qq_disable_temp_session", True, table_name="bot_aiocqhttp")
enable_listening_self_message = Config("qq_enable_listening_self_message", False, table_name="bot_aiocqhttp")


@aiocqhttp_bot.on_startup
async def startup():
    await client_init(target_prefix_list, sender_prefix_list)
    asyncio.create_task(AIOCQFetchedContextManager.process_tasks())
    aiocqhttp_bot.logger.setLevel(logging.WARNING)


@aiocqhttp_bot.on_websocket_connection
async def _(event: Event):
    qq_login_info = await aiocqhttp_bot.call_action("get_login_info")
    qq_account = qq_login_info.get("user_id")
    Temp.data["qq_account"] = str(qq_account)
    Temp.data["qq_nickname"] = qq_login_info.get("nickname")
    Temp.data["onebot_impl"] = await get_onebot_implementation()


async def message_handler(event: Event):
    if event.detail_type == "private" and event.sub_type == "group" \
            and disable_temp_session:
        return

    if event.group_id:
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
            load_json = orjson.loads(html.unescape(match_json.group(1)))
            if load_json["app"] == "com.tencent.multimsg":
                event.message = f"[CQ:forward,id={load_json["meta"]["detail"]["resid"]}]"
    else:
        if event.message[0]["type"] == "json":
            load_json = orjson.loads(event.message[0]["data"]["data"])
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

    at_message = False
    if string_post:
        if match_at := re.match(r"^\[CQ:at,qq=(\d+).*\](.*)", event.message):
            if match_at.group(1) == str(event.self_id):
                at_message = True
                event.message = match_at.group(2).strip()
                if not event.message:
                    event.message = f"{command_prefix[0]}help"
            else:
                return
    else:
        if event.message[0]["type"] == "at":
            if event.message[0]["data"]["qq"] == str(event.self_id):
                at_message = True
                event.message = event.message[1:]
                if not event.message or \
                        event.message[0]["type"] == "text" and not event.message[0]["data"]["text"].strip():
                    event.message = [{"type": "text", "data": {"text": f"{command_prefix[0]}help"}}]
            else:
                return
    if mention_required and not at_message and event.detail_type == "group":
        return

    msg_chain = await to_message_chain(event.message)

    sender_name = None

    if event.sender:
        sender_name = event.sender.get("nickname")

    session = await SessionInfo.assign(target_id=target_id,
                                       sender_id=sender_id,
                                       target_from=target_group_prefix if event.detail_type == "group" else target_private_prefix,
                                       sender_from=sender_prefix,
                                       sender_name=sender_name,
                                       client_name=client_name,
                                       message_id=str(event.message_id),
                                       reply_id=str(reply_id),
                                       messages=msg_chain,
                                       ctx_slot=ctx_id,
                                       use_url_manager=use_url_manager,
                                       require_check_dirty_words=dirty_word_check,
                                       tmp=Temp.data.copy()
                                       )

    await Bot.process_message(session, event)


if enable_listening_self_message:
    @aiocqhttp_bot.on("message_sent")
    async def _(event: Event):
        await message_handler(event)


@aiocqhttp_bot.on_message("group", "private")
async def _(event: Event):
    await message_handler(event)


@aiocqhttp_bot.on("notice.notify")
async def _(event: Event):
    if event.sub_type == "poke" and quick_confirm:
        event.message = confirm_command_default[0]
        await message_handler(event)


@aiocqhttp_bot.on("notice.group_msg_emoji_like")
async def _(event: Event):
    # API 假定点赞消息只能由自己收到
    if event.likes:
        like = event.likes[0]
        try:
            char = chr(int(like["emoji_id"]))
            if not emoji.is_emoji(char):
                raise ValueError
            emoji_ = char
        except (ValueError, OverflowError):
            emoji_ = f"[CQ:face,id={like["emoji_id"]}]"

        if event.group_id:
            target_id = f"{target_group_prefix}|{event.group_id}"
        else:
            target_id = f"{target_private_prefix}|{event.user_id}"
        sender_id = f"{sender_prefix}|{event.user_id}"

        if sender_id in ignored_sender:
            return

        sender_name = None

        if event.sender:
            sender_name = event.sender.get("nickname")
        session = await SessionInfo.assign(target_id=target_id,
                                           sender_id=sender_id,
                                           target_from=target_group_prefix if event.detail_type == "group" else target_private_prefix,
                                           sender_from=sender_prefix,
                                           sender_name=sender_name,
                                           client_name=client_name,
                                           reply_id=str(event.message_id),
                                           messages=MessageChain.assign([Plain(emoji_)]),
                                           ctx_slot=ctx_id
                                           )

        await Bot.process_message(session, event)


@aiocqhttp_bot.on("request.friend")
async def _(event: Event):
    sender_id = f"{sender_prefix}|{event.user_id}"
    sender_info = await SenderInfo.get_by_sender_id(sender_id)
    if sender_info.superuser or sender_info.trusted:
        return {"approve": True}
    if Config("qq_allow_approve_friend", False, table_name="bot_aiocqhttp"):
        if sender_info.blocked:
            return {"approve": False}
        return {"approve": True}
    return {"approve": False}


@aiocqhttp_bot.on("request.group.invite")
async def _(event: Event):
    sender_id = f"{sender_prefix}|{event.user_id}"
    sender_info = await SenderInfo.get_by_sender_id(sender_id)
    target_id = f"{target_group_prefix}|{event.group_id}"
    target_info = await TargetInfo.get_by_target_id(target_id)
    if sender_info.superuser or sender_info.trusted:
        return {"approve": True}
    if Config("qq_allow_approve_group_invite", False, table_name="bot_aiocqhttp"):
        if target_info.blocked:
            return {"approve": False}
        return {"approve": True}


@aiocqhttp_bot.on_notice("group_ban")
async def _(event: Event):
    if enable_tos and event.sub_type == "ban" and event.user_id == int(event.self_id):
        sender_id = f"{sender_prefix}|{event.operator_id}"
        sender_info = await SenderInfo.get_by_sender_id(sender_id)
        target_id = f"{target_group_prefix}|{event.group_id}"
        target_info = await TargetInfo.get_by_target_id(target_id)
        if event.duration > 0:
            await UnfriendlyActionRecords.create(target_id=target_id,
                                                 sender_id=sender_id,
                                                 action="restrict",
                                                 detail=str(event.duration))
            Logger.info(f"Unfriendly action detected: restrict ({event.duration})")
        result = await UnfriendlyActionRecords.check_mute(target_id=target_id)
        if event.duration >= 259200:  # 3 days
            result = True
        if result and not sender_info.superuser:
            Logger.info(f"Ban {sender_id} ({target_id}) by ToS: restrict")
            Logger.info(f"Block {target_id} by ToS: restrict")
            reason = Locale(default_locale).t("tos.message.reason.restrict")
            await tos_report(sender_id, target_id, reason, banned=True)
            await target_info.edit_attr("blocked", True)
            await aiocqhttp_bot.call_action("set_group_leave", group_id=event.group_id)
            await sender_info.switch_identity(trust=False)
            await aiocqhttp_bot.call_action("delete_friend", friend_id=event.operator_id)


@aiocqhttp_bot.on_notice("group_decrease")
async def _(event: Event):
    if enable_tos and event.sub_type == "kick_me":
        sender_id = f"{sender_prefix}|{event.operator_id}"
        sender_info = await SenderInfo.get_by_sender_id(sender_id)
        target_id = f"{target_group_prefix}|{event.group_id}"
        target_info = await TargetInfo.get_by_target_id(target_id)
        await UnfriendlyActionRecords.create(target_id=target_id,
                                             sender_id=sender_id,
                                             action="kick",
                                             detail="")
        Logger.info("Unfriendly action detected: kick")
        if not sender_info.superuser:
            Logger.info(f"Ban {sender_id} ({target_id}) by ToS: kick")
            Logger.info(f"Block {target_id} by ToS: kick")
            reason = Locale(default_locale).t("tos.message.reason.kick")
            await tos_report(sender_id, target_id, reason, banned=True)
            await target_info.edit_attr("blocked", True)
            await sender_info.switch_identity(trust=False)
            await aiocqhttp_bot.call_action("delete_friend", friend_id=event.operator_id)


@aiocqhttp_bot.on_message("group")
async def _(event: Event):
    if enable_tos:
        target_id = f"{target_group_prefix}|{event.group_id}"
        target_info = await TargetInfo.get_by_target_id(target_id, create=False)
        if target_info and target_info.blocked:
            res = Locale(default_locale).t("tos.message.in_group_blocklist")
            if issue_url := Config("issue_url", issue_url_default):
                res += "\n" + Locale(default_locale).t("tos.message.appeal", issue_url=issue_url)
            await aiocqhttp_bot.send(event=event, message=res)
            await aiocqhttp_bot.call_action("set_group_leave", group_id=event.group_id)


qq_host = Config("qq_host", default=qq_host_default, table_name="bot_aiocqhttp")
if Config("enable", False, table_name="bot_aiocqhttp"):
    HyperConfig.startup_timeout = 120
    host, port = qq_host.split(":")
    aiocqhttp_bot.run(host=host, port=port, debug=False)
