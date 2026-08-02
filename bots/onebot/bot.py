import asyncio
import html
import logging
import re

import emoji
import orjson
from aiocqhttp import Event
from hypercorn import Config as HyperConfig

from bots.onebot.client import aiocqhttp_bot
from bots.onebot.context import OneBotContextManager, OneBotFetchedContextManager
from bots.onebot.info import *
from bots.onebot.utils import to_message_chain, get_onebot_implementation
from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import Plain
from core.builtins.session.info import SessionInfo
from core.builtins.temp import Temp
from core.builtins.utils import command_prefix
from core.client.init import client_init
from bots.onebot.config import AiocqhttpConfig
from core.config.base import BaseConfig, CoreConfig
from core.constants.default import confirm_command_default
from core.database.models import SenderUnionInfo, TargetUnionInfo, UnfriendlyActionRecords
from core.i18n import Locale
from core.logger import Logger
from core.retired import is_retired_client
from core.tos import tos_report

Bot.register_bot(client_name=client_name)
ctx_id = Bot.register_context_manager(OneBotContextManager)
Bot.register_context_manager(OneBotFetchedContextManager, fetch_session=True)

default_locale = BaseConfig.default_locale
ignored_sender = CoreConfig.ignored_sender
enable_tos = CoreConfig.enable_tos
mention_required = CoreConfig.mention_required
quick_confirm = CoreConfig.quick_confirm

# 本平台退役后不再追究针对机器人自身的不友好行为。退役实例已停止服务，将机器人禁言或移出群聊
# 是管理员的正常处置，不应据此追责；且迁移完成后两侧的账号与场景同属一个 union，在此处封禁会
# 连带波及用户在新平台上的身份，把一次合理的清退变成对已迁移用户的误封。
client_retired = is_retired_client(client_name)

enable_temp_session = AiocqhttpConfig.qq_enable_temp_session
enable_listening_self_message = AiocqhttpConfig.qq_enable_listening_self_message
qq_account = None


@aiocqhttp_bot.on_startup
async def startup():
    await client_init(target_prefix_list, sender_prefix_list)
    asyncio.create_task(OneBotFetchedContextManager.process_tasks())
    aiocqhttp_bot.logger.setLevel(logging.WARNING)


@aiocqhttp_bot.on_websocket_connection
async def _(event: Event):
    qq_login_info = await aiocqhttp_bot.call_action("get_login_info")
    global qq_account
    qq_account = qq_login_info.get("user_id")
    Temp.data["qq_account"] = str(qq_account)
    Temp.data["qq_nickname"] = qq_login_info.get("nickname")
    Temp.data["onebot_impl"] = await get_onebot_implementation()


async def message_handler(event: Event):
    if event.detail_type == "private" and event.sub_type == "group" and not enable_temp_session:
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
            if load_json.get("app") == "com.tencent.multimsg":
                event.message = f"[CQ:forward,id={load_json.get('meta', {}).get('detail', {}).get('resid', '')}]"
    else:
        if event.message and event.message[0]["type"] == "json":
            load_json = orjson.loads(event.message[0]["data"]["data"])
            if load_json.get("app") == "com.tencent.multimsg":
                event.message = [
                    {
                        "type": "forward",
                        "data": {"id": f"{load_json.get('meta', {}).get('detail', {}).get('resid', '')}"},
                    }
                ]

    reply_id = None
    if string_post:
        match_reply = re.match(r"^\[CQ:reply,id=(-?\d+).*\].*", event.message)
        if match_reply:
            reply_id = int(match_reply.group(1))
    else:
        if event.message and event.message[0]["type"] == "reply":
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
        if event.message and event.message[0]["type"] == "at":
            if event.message[0]["data"]["qq"] == str(event.self_id):
                at_message = True
                event.message = event.message[1:]
                if (
                    not event.message
                    or event.message[0]["type"] == "text"
                    and not event.message[0]["data"]["text"].strip()
                ):
                    event.message = [{"type": "text", "data": {"text": f"{command_prefix[0]}help"}}]
            else:
                return
    if mention_required and not at_message and event.detail_type == "group":
        return

    msg_chain = await to_message_chain(event.message)

    sender_name = None

    if event.sender:
        sender_name = event.sender.get("nickname")

    session = await SessionInfo.assign(
        target_id=target_id,
        sender_id=sender_id,
        target_from=target_group_prefix if event.detail_type == "group" else target_private_prefix,
        is_private=event.detail_type != "group",
        sender_from=sender_prefix,
        sender_name=sender_name,
        client_name=client_name,
        message_id=str(event.message_id),
        reply_id=str(reply_id),
        messages=msg_chain,
        ctx_slot=ctx_id,
        tmp=Temp.data.copy(),
        bot_id=str(qq_account),
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
            emoji_ = f"[CQ:face,id={like['emoji_id']}]"

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
        session = await SessionInfo.assign(
            target_id=target_id,
            sender_id=sender_id,
            target_from=target_group_prefix if event.detail_type == "group" else target_private_prefix,
            is_private=event.detail_type != "group",
            sender_from=sender_prefix,
            sender_name=sender_name,
            client_name=client_name,
            reply_id=str(event.message_id),
            messages=MessageChain.assign([Plain(emoji_)]),
            ctx_slot=ctx_id,
            bot_id=str(qq_account),
        )

        await Bot.process_message(session, event)


@aiocqhttp_bot.on("request.friend")
async def _(event: Event):
    sender_id = f"{sender_prefix}|{event.user_id}"
    sender_union_info = await SenderUnionInfo.get_by_sender_id(sender_id)
    if sender_union_info.superuser or sender_union_info.trusted:
        return {"approve": True}
    if AiocqhttpConfig.qq_allow_approve_friend:
        if sender_union_info.blocked:
            return {"approve": False}
        return {"approve": True}
    return {"approve": False}


@aiocqhttp_bot.on("request.group.invite")
async def _(event: Event):
    sender_id = f"{sender_prefix}|{event.user_id}"
    sender_union_info = await SenderUnionInfo.get_by_sender_id(sender_id)
    target_id = f"{target_group_prefix}|{event.group_id}"
    target_union_info = await TargetUnionInfo.get_by_target_id(target_id)
    if sender_union_info.superuser or sender_union_info.trusted:
        return {"approve": True}
    if AiocqhttpConfig.qq_allow_approve_group_invite:
        if target_union_info.blocked:
            return {"approve": False}
        return {"approve": True}


@aiocqhttp_bot.on_notice("group_ban")
async def _(event: Event):
    if enable_tos and not client_retired and event.sub_type == "ban" and event.user_id == int(event.self_id):
        sender_id = f"{sender_prefix}|{event.operator_id}"
        sender_union_info = await SenderUnionInfo.get_by_sender_id(sender_id)
        target_id = f"{target_group_prefix}|{event.group_id}"
        target_union_info = await TargetUnionInfo.get_by_target_id(target_id)
        if event.duration > 0:
            await UnfriendlyActionRecords.create(
                target_id=target_id,
                sender_id=sender_id,
                target_union_id=target_union_info.union_id,
                sender_union_id=sender_union_info.union_id,
                action="restrict",
                detail=str(event.duration),
            )
            Logger.info(f"Unfriendly action detected: restrict ({event.duration})")
        result = await UnfriendlyActionRecords.check_mute(target_id=target_id)
        if event.duration >= 259200:  # 3 days
            result = True
        if result and not sender_union_info.superuser:
            Logger.info(f"Ban {sender_id} ({target_id}) by ToS: restrict")
            Logger.info(f"Block {target_id} by ToS: restrict")
            reason = Locale(default_locale).t("tos.message.reason.restrict")
            await tos_report(sender_id, target_id, reason, banned=True)
            await target_union_info.edit_attr("blocked", True)
            await aiocqhttp_bot.call_action("set_group_leave", group_id=event.group_id)
            await sender_union_info.switch_identity(trust=False)
            await aiocqhttp_bot.call_action("delete_friend", friend_id=event.operator_id)


@aiocqhttp_bot.on_notice("group_decrease")
async def _(event: Event):
    if enable_tos and not client_retired and event.sub_type == "kick_me":
        sender_id = f"{sender_prefix}|{event.operator_id}"
        sender_union_info = await SenderUnionInfo.get_by_sender_id(sender_id)
        target_id = f"{target_group_prefix}|{event.group_id}"
        target_union_info = await TargetUnionInfo.get_by_target_id(target_id)
        await UnfriendlyActionRecords.create(
            target_id=target_id,
            sender_id=sender_id,
            target_union_id=target_union_info.union_id,
            sender_union_id=sender_union_info.union_id,
            action="kick",
            detail="",
        )
        Logger.info("Unfriendly action detected: kick")
        if not sender_union_info.superuser:
            Logger.info(f"Ban {sender_id} ({target_id}) by ToS: kick")
            Logger.info(f"Block {target_id} by ToS: kick")
            reason = Locale(default_locale).t("tos.message.reason.kick")
            await tos_report(sender_id, target_id, reason, banned=True)
            await target_union_info.edit_attr("blocked", True)
            await sender_union_info.switch_identity(trust=False)
            await aiocqhttp_bot.call_action("delete_friend", friend_id=event.operator_id)


@aiocqhttp_bot.on_message("group")
async def _(event: Event):
    if enable_tos:
        target_id = f"{target_group_prefix}|{event.group_id}"
        target_union_info = await TargetUnionInfo.get_by_target_id(target_id, create=False)
        if target_union_info and target_union_info.blocked:
            res = Locale(default_locale).t("tos.message.in_group_blocklist")
            if issue_url := CoreConfig.issue_url:
                res += "\n" + Locale(default_locale).t("tos.message.appeal", issue_url=issue_url)
            await aiocqhttp_bot.send(event=event, message=res)
            await aiocqhttp_bot.call_action("set_group_leave", group_id=event.group_id)


qq_host = AiocqhttpConfig.qq_host
if AiocqhttpConfig.enable:
    HyperConfig.startup_timeout = 120
    host, port = qq_host.split(":")
    aiocqhttp_bot.run(host=host, port=port, debug=False)
