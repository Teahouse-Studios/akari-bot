import asyncio

from bots.milky.client import milky_bot
from bots.milky.config import MilkyConfig
from bots.milky.context import MilkyContextManager, MilkyFetchedContextManager
from bots.milky.info import *
from bots.milky.utils import MILKY_IMPL_TEMP_KEY, get_milky_implementation, message_field, to_message_chain
from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.session.info import SessionInfo
from core.builtins.temp import Temp
from core.builtins.utils import command_prefix
from core.client.init import client_cleanup, client_init
from core.config.base import BaseConfig, CoreConfig
from core.constants.default import confirm_command_default
from core.database.models import SenderUnionInfo, TargetUnionInfo, UnfriendlyActionRecords
from core.i18n import Locale
from core.logger import Logger
from core.queue.contracts import ServerAPI
from core.utils.retired import is_retired_client

Bot.register_bot(client_name=client_name)
ctx_id = Bot.register_context_manager(MilkyContextManager)
Bot.register_context_manager(MilkyFetchedContextManager, fetch_session=True)

default_locale = BaseConfig.default_locale
ignored_sender = CoreConfig.ignored_sender
enable_tos = CoreConfig.enable_tos
mention_required = CoreConfig.mention_required
quick_confirm = CoreConfig.quick_confirm

# 本平台退役后不再追究针对机器人自身的不友好行为。退役实例已停止服务，将机器人禁言或移出群聊
# 是管理员的正常处置，不应据此追责；且迁移完成后两侧的账号与场景同属一个 union，在此处封禁会
# 连带波及用户在新平台上的身份，把一次合理的清退变成对已迁移用户的误封。
client_retired = is_retired_client(client_name)

enable_temp_session = MilkyConfig.qq_enable_temp_session
enable_listening_self_message = MilkyConfig.qq_enable_listening_self_message
# 事件流断开后的重连间隔，避免协议端未就绪时形成空转
EVENT_RECONNECT_DELAY = 5
milky_account: int | None = None


async def _tos_report(sender: str, target: str, reason: str, banned: bool = False):
    try:
        return await ServerAPI.trigger_hook(
            "tos.report",
            session_info=None,
            sender=sender,
            target=target,
            reason=reason,
            banned=banned,
        )
    except Exception:
        Logger.exception(f"tos.report hook failed; report dropped (sender={sender}, target={target}).")
        return None


def _event_data(event: dict) -> dict:
    data = event.get("data")
    return data if isinstance(data, dict) else {}


def _is_self(user_id) -> bool:
    if milky_account is None or user_id is None:
        return False
    return str(user_id) == str(milky_account)


def _sender_name(message: dict) -> str | None:
    member = message_field(message, "group_member") or {}
    friend = message_field(message, "friend") or {}
    return member.get("card") or member.get("nickname") or friend.get("nickname") or None


async def refresh_login_info() -> None:
    global milky_account
    login_info = await milky_bot.get_login_info()
    milky_account = login_info.uin
    Temp.data["qq_account"] = str(milky_account) if milky_account is not None else None
    Temp.data["qq_nickname"] = login_info.nickname
    Temp.data[MILKY_IMPL_TEMP_KEY] = await get_milky_implementation()
    Logger.info(f"Milky bot logged in as {login_info.nickname} ({milky_account}).")


async def _assign_session(
    context: str,
    peer_id,
    sender_uin,
    messages: MessageChain,
    sender_name: str | None = None,
    message_id: str | None = None,
    reply_id: str | None = None,
) -> SessionInfo:
    is_group = context == "group"
    return await SessionInfo.assign(
        target_id=f"{target_group_prefix}|{peer_id}" if is_group else f"{target_private_prefix}|{sender_uin}",
        sender_id=f"{sender_prefix}|{sender_uin}",
        target_from=target_group_prefix if is_group else target_private_prefix,
        is_private=not is_group,
        sender_from=sender_prefix,
        sender_name=sender_name,
        client_name=client_name,
        message_id=message_id,
        reply_id=reply_id,
        messages=messages,
        ctx_slot=ctx_id,
        tmp=Temp.data.copy(),
        bot_id=str(milky_account) if milky_account is not None else None,
    )


def _has_content(segments: list[dict]) -> bool:
    for segment in segments:
        if segment.get("type") != "text":
            return True
        if str((segment.get("data") or {}).get("text") or "").strip():
            return True
    return False


async def _process_synthetic_message(
    context: str,
    peer_id,
    sender_uin,
    text: str,
    source_event: dict,
    message_id: str | None = None,
    reply_id: str | None = None,
) -> None:
    msg_chain = await to_message_chain({"segments": [{"type": "text", "data": {"text": text}}]})
    session = await _assign_session(
        context=context,
        peer_id=peer_id,
        sender_uin=sender_uin,
        messages=msg_chain,
        message_id=message_id,
        reply_id=reply_id,
    )
    await Bot.process_message(session, source_event)


async def _enforce_group_blocklist(session: SessionInfo, context: str, peer_id) -> None:
    if not enable_tos or context != "group":
        return
    target_id = f"{target_group_prefix}|{peer_id}"
    target_union_info = await TargetUnionInfo.get_by_target_id(target_id, create=False)
    if not (target_union_info and target_union_info.blocked):
        return
    res = Locale(default_locale).t("tos.message.in_group_blocklist")
    if issue_url := CoreConfig.issue_url:
        res += "\n" + Locale(default_locale).t("tos.message.appeal", issue_url=issue_url)
    await MilkyContextManager.send_message(session, MessageChain.assign(res), quote=False)
    await milky_bot.quit_group(group_id=int(peer_id))


async def message_handler(event: dict) -> None:
    """处理消息接收事件。"""
    message = _event_data(event)
    context = message_field(message, "message_scene")
    sender_uin = message_field(message, "sender_id")
    if context == "temp" and not enable_temp_session:
        return
    if _is_self(sender_uin) and not enable_listening_self_message:
        return

    sender_id = f"{sender_prefix}|{sender_uin}"
    if sender_id in ignored_sender:
        return

    raw_segments = [segment for segment in (message_field(message, "segments") or []) if isinstance(segment, dict)]
    segments = list(raw_segments)
    at_message = False
    if segments and segments[0].get("type") == "mention":
        mentioned = (segments[0].get("data") or {}).get("user_id")
        if not _is_self(mentioned):
            # 消息以 @ 他人开头时视为与机器人无关
            return
        at_message = True
        segments = segments[1:]
        if not _has_content(segments):
            segments = [{"type": "text", "data": {"text": f"{command_prefix[0]}help"}}]
    if mention_required and not at_message and context == "group":
        return

    reply_id = None
    for segment in raw_segments:
        if segment.get("type") == "reply":
            reply_id = (segment.get("data") or {}).get("message_seq")
            break

    message_seq = message_field(message, "message_seq")
    session = await _assign_session(
        context=context,
        peer_id=message_field(message, "peer_id"),
        sender_uin=sender_uin,
        messages=await to_message_chain({"segments": segments}),
        sender_name=_sender_name(message),
        message_id=str(message_seq) if message_seq is not None else None,
        reply_id=str(reply_id) if reply_id is not None else None,
    )

    await Bot.process_message(session, event)

    await _enforce_group_blocklist(session, context, message_field(message, "peer_id"))


async def friend_request_handler(event: dict) -> None:
    message = _event_data(event)
    initiator_uid = message_field(message, "initiator_uid")
    if not initiator_uid:
        return
    is_filtered = bool(message_field(message, "is_filtered", False))
    sender_id = f"{sender_prefix}|{message_field(message, 'initiator_id')}"
    sender_union_info = await SenderUnionInfo.get_by_sender_id(sender_id)
    if sender_union_info.superuser or sender_union_info.trusted:
        await milky_bot.accept_friend_request(initiator_uid, is_filtered=is_filtered)
        return
    if MilkyConfig.qq_allow_approve_friend and not sender_union_info.blocked:
        await milky_bot.accept_friend_request(initiator_uid, is_filtered=is_filtered)
        return
    await milky_bot.reject_friend_request(initiator_uid, is_filtered=is_filtered)


async def group_invitation_handler(event: dict) -> None:
    message = _event_data(event)
    group_id = message_field(message, "group_id")
    invitation_seq = message_field(message, "invitation_seq")
    if group_id is None or invitation_seq is None:
        return
    sender_id = f"{sender_prefix}|{message_field(message, 'initiator_id')}"
    sender_union_info = await SenderUnionInfo.get_by_sender_id(sender_id)
    if sender_union_info.superuser or sender_union_info.trusted:
        await milky_bot.accept_group_invitation(group_id=group_id, invitation_seq=invitation_seq)
        return
    if not MilkyConfig.qq_allow_approve_group_invite:
        # 未开启自动同意时保持请求待处理，交由管理员处理
        return
    target_id = f"{target_group_prefix}|{group_id}"
    target_union_info = await TargetUnionInfo.get_by_target_id(target_id)
    if target_union_info.blocked:
        await milky_bot.reject_group_invitation(group_id=group_id, invitation_seq=invitation_seq)
        return
    await milky_bot.accept_group_invitation(group_id=group_id, invitation_seq=invitation_seq)


async def group_nudge_handler(event: dict) -> None:
    message = _event_data(event)
    if not quick_confirm or not _is_self(message_field(message, "receiver_id")):
        return
    await _process_synthetic_message(
        context="group",
        peer_id=message_field(message, "group_id"),
        sender_uin=message_field(message, "sender_id"),
        text=confirm_command_default[0],
        source_event=event,
    )


async def friend_nudge_handler(event: dict) -> None:
    message = _event_data(event)
    if not quick_confirm or not message_field(message, "is_self_receive", False):
        return
    await _process_synthetic_message(
        context="friend",
        peer_id=message_field(message, "user_id"),
        sender_uin=message_field(message, "user_id"),
        text=confirm_command_default[0],
        source_event=event,
    )


async def group_mute_handler(event: dict) -> None:
    if not (enable_tos and not client_retired):
        return
    message = _event_data(event)
    if not _is_self(message_field(message, "user_id")):
        return
    duration = int(message_field(message, "duration", 0) or 0)
    if duration <= 0:
        # 解除禁言不是不友好行为
        return
    group_id = message_field(message, "group_id")
    sender_id = f"{sender_prefix}|{message_field(message, 'operator_id')}"
    sender_union_info = await SenderUnionInfo.get_by_sender_id(sender_id)
    target_id = f"{target_group_prefix}|{group_id}"
    target_union_info = await TargetUnionInfo.get_by_target_id(target_id)
    await UnfriendlyActionRecords.create(
        target_id=target_id,
        sender_id=sender_id,
        target_union_id=target_union_info.union_id,
        sender_union_id=sender_union_info.union_id,
        action="restrict",
        detail=str(duration),
    )
    Logger.info(f"Unfriendly action detected: restrict ({duration})")
    result = await UnfriendlyActionRecords.check_mute(target_id=target_id)
    if duration >= 259200:  # 3 days
        result = True
    if result and not sender_union_info.superuser:
        Logger.info(f"Ban {sender_id} ({target_id}) by ToS: restrict")
        Logger.info(f"Block {target_id} by ToS: restrict")
        reason = Locale(default_locale).t("tos.message.reason.restrict")
        await _tos_report(sender_id, target_id, reason, banned=True)
        await target_union_info.edit_attr("blocked", True)
        await milky_bot.quit_group(group_id=int(group_id))
        await sender_union_info.switch_identity(trust=False)
        # Milky SDK 未提供删除好友接口，无法像 OneBot 一样同时解除好友关系


async def group_member_decrease_handler(event: dict) -> None:
    if not (enable_tos and not client_retired):
        return
    message = _event_data(event)
    if not _is_self(message_field(message, "user_id")):
        return
    operator_id = message_field(message, "operator_id")
    if not operator_id:
        # 自主退群或协议端未提供操作者时无法归因，不视为不友好行为
        return
    group_id = message_field(message, "group_id")
    sender_id = f"{sender_prefix}|{operator_id}"
    sender_union_info = await SenderUnionInfo.get_by_sender_id(sender_id)
    target_id = f"{target_group_prefix}|{group_id}"
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
        await _tos_report(sender_id, target_id, reason, banned=True)
        await target_union_info.edit_attr("blocked", True)
        await sender_union_info.switch_identity(trust=False)


async def bot_offline_handler(event: dict) -> None:
    reason = message_field(_event_data(event), "reason", "") or "unknown reason"
    Logger.error(f"Milky bot went offline: {reason}")


EVENT_HANDLERS = {
    "message_receive": message_handler,
    "friend_request": friend_request_handler,
    "friend_nudge": friend_nudge_handler,
    "group_invitation": group_invitation_handler,
    "group_nudge": group_nudge_handler,
    "group_mute": group_mute_handler,
    "group_member_decrease": group_member_decrease_handler,
    "bot_offline": bot_offline_handler,
}


async def dispatch_event(event: dict) -> None:
    """按事件类型分发单个 Milky 事件。

    :param event: Milky 原始事件。
    """
    event_type = event.get("event_type")
    handler = EVENT_HANDLERS.get(str(event_type))
    if handler is None:
        Logger.debug(f"Ignored Milky event: {event_type}")
        return
    try:
        await handler(event)
    except asyncio.CancelledError:
        raise
    except Exception:
        Logger.exception(f"Failed to handle Milky event {event_type}: ")


async def event_loop() -> None:
    while True:
        try:
            async for event in milky_bot.events_sse():
                if isinstance(event, dict):
                    await dispatch_event(event)
        except asyncio.CancelledError:
            raise
        except Exception:
            Logger.exception("Milky event stream stopped unexpectedly, reconnecting: ")
        else:
            Logger.warning("Milky event stream closed by the protocol side, reconnecting.")
        await asyncio.sleep(EVENT_RECONNECT_DELAY)


async def startup() -> None:
    """初始化客户端队列、主动消息 worker 与机器人自身信息。"""
    await client_init(target_prefix_list, sender_prefix_list)
    MilkyFetchedContextManager.start_task_processor()
    await refresh_login_info()


async def shutdown() -> None:
    """依次停止主动消息 worker、输入状态任务、HTTP 客户端与客户端队列。"""
    try:
        await MilkyFetchedContextManager.stop_task_processor()
    finally:
        try:
            await MilkyContextManager.shutdown()
        finally:
            try:
                await milky_bot.close()
            finally:
                await client_cleanup()


async def main() -> None:
    await startup()
    try:
        await event_loop()
    finally:
        await shutdown()


if MilkyConfig.enable:
    asyncio.run(main())
