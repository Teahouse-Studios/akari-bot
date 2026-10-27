from bots.kook.info import (
    client_name,
    sender_prefix,
    target_group_prefix,
    target_guild_prefix,
    target_person_prefix,
)
from core.builtins.bot import Bot
from core.builtins.session.info import EventInfo
from core.logger import Logger


async def guild_member_joined(
    member_id: str | int,
    guild_id: str | int,
    joined_at: int | None = None,
    event_id: str | None = None,
):
    """将 KOOK 服务器成员加入通知转换为核心事件。"""
    data = {}
    if joined_at is not None:
        data["joined_at"] = joined_at
    if event_id is not None:
        data["event_id"] = event_id

    event_info = await EventInfo.assign(
        event_name="guild_member_joined",
        target_id=f"{target_guild_prefix}|{guild_id}",
        target_from=target_guild_prefix,
        client_name=client_name,
        sender_id=f"{sender_prefix}|{member_id}",
        sender_from=sender_prefix,
        data=data,
    )
    return await Bot.process_event(event_info)


async def guild_member_left(
    member_id: str | int,
    guild_id: str | int,
    left_at: int | None = None,
    event_id: str | None = None,
):
    """将 KOOK 服务器成员离开通知转换为核心事件。"""
    data = {}
    if left_at is not None:
        data["left_at"] = left_at
    if event_id is not None:
        data["event_id"] = event_id

    event_info = await EventInfo.assign(
        event_name="guild_member_left",
        target_id=f"{target_guild_prefix}|{guild_id}",
        target_from=target_guild_prefix,
        client_name=client_name,
        sender_id=f"{sender_prefix}|{member_id}",
        sender_from=sender_prefix,
        data=data,
    )
    return await Bot.process_event(event_info)


async def message_recalled(
    message_id: str | int | None,
    user_id: str | int,
    group_id: str | int | None = None,
):
    """将 KOOK 消息删除通知转换为核心事件。"""
    if message_id is None:
        return None
    if group_id is not None:
        target_id = f"{target_group_prefix}|{group_id}"
        target_from = target_group_prefix
    else:
        target_id = f"{target_person_prefix}|{user_id}"
        target_from = target_person_prefix
    try:
        event_info = await EventInfo.assign(
            event_name="message_recalled",
            target_id=target_id,
            target_from=target_from,
            client_name=client_name,
            sender_id=f"{sender_prefix}|{user_id}",
            sender_from=sender_prefix,
            data={"message_id": str(message_id)},
            create=False,
        )
    except ValueError:
        # 未记录过的场景不因撤回事件建立身份数据。
        Logger.debug(f"Ignored recall from unknown target {target_id}.")
        return None
    return await Bot.process_event(event_info)
