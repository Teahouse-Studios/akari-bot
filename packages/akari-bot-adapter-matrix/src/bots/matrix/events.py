from bots.matrix.info import client_name, sender_prefix, target_prefix
from core.builtins.bot import Bot
from core.builtins.session.info import EventInfo


def should_dispatch_member_joined(
    *,
    initial_sync_complete: bool,
    member_id: str,
    bot_id: str,
    membership: str,
    prev_membership: str | None,
    sender_id: str,
    ignored_sender: list[str],
) -> bool:
    """过滤首次全量同步、重复 join 状态、机器人自身及忽略用户。"""
    return (
        initial_sync_complete
        and membership == "join"
        and prev_membership != "join"
        and member_id != bot_id
        and sender_id not in ignored_sender
    )


def should_dispatch_member_left(
    *,
    initial_sync_complete: bool,
    member_id: str,
    bot_id: str,
    membership: str,
    prev_membership: str | None,
    sender_id: str,
    ignored_sender: list[str],
) -> bool:
    """只处理真实成员从 join 状态离开或被移出房间的变化。"""
    return (
        initial_sync_complete
        and membership in {"leave", "ban"}
        and prev_membership == "join"
        and member_id != bot_id
        and sender_id not in ignored_sender
    )


async def member_joined(
    member_id: str,
    room_id: str,
    event_id: str | None = None,
):
    """将 Matrix 房间成员加入通知转换为核心事件。"""
    data = {}
    if event_id is not None:
        data["event_id"] = event_id

    event_info = await EventInfo.assign(
        event_name="member_joined",
        target_id=f"{target_prefix}|{room_id}",
        target_from=target_prefix,
        client_name=client_name,
        sender_id=f"{sender_prefix}|{member_id.removeprefix('@')}",
        sender_from=sender_prefix,
        data=data,
    )
    return await Bot.process_event(event_info)


async def member_left(
    member_id: str,
    room_id: str,
    event_id: str | None = None,
):
    """将 Matrix 房间成员离开通知转换为核心事件。"""
    data = {}
    if event_id is not None:
        data["event_id"] = event_id

    event_info = await EventInfo.assign(
        event_name="member_left",
        target_id=f"{target_prefix}|{room_id}",
        target_from=target_prefix,
        client_name=client_name,
        sender_id=f"{sender_prefix}|{member_id.removeprefix('@')}",
        sender_from=sender_prefix,
        data=data,
    )
    return await Bot.process_event(event_info)
