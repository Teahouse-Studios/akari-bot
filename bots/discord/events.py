from datetime import datetime

from bots.discord.info import client_name, sender_prefix, target_guild_prefix
from core.builtins.bot import Bot
from core.builtins.session.info import EventInfo
from core.logger import Logger


async def guild_member_joined(
    member_id: str | int,
    guild_id: str | int,
    joined_at: datetime | None = None,
):
    """将 Discord 服务器成员加入通知转换为核心事件。"""
    data = {}
    if joined_at is not None:
        data["joined_at"] = joined_at.isoformat()

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


async def guild_member_left(member_id: str | int, guild_id: str | int):
    """将 Discord 服务器成员离开通知转换为核心事件。"""
    event_info = await EventInfo.assign(
        event_name="guild_member_left",
        target_id=f"{target_guild_prefix}|{guild_id}",
        target_from=target_guild_prefix,
        client_name=client_name,
        sender_id=f"{sender_prefix}|{member_id}",
        sender_from=sender_prefix,
    )
    return await Bot.process_event(event_info)


async def message_recalled(
    message_id: str | int,
    channel_id: str | int,
    target_from: str,
    author_id: str | int | None = None,
):
    """将 Discord 消息删除通知转换为核心事件。"""
    sender_id = f"{sender_prefix}|{author_id}" if author_id is not None else None
    try:
        event_info = await EventInfo.assign(
            event_name="message_recalled",
            target_id=f"{target_from}|{channel_id}",
            target_from=target_from,
            client_name=client_name,
            sender_id=sender_id,
            sender_from=sender_prefix if sender_id else None,
            data={"message_id": str(message_id)},
            create=False,
        )
    except ValueError:
        # 未记录过的场景不因撤回事件建立身份数据。
        Logger.debug(f"Ignored recall from unknown channel {channel_id}.")
        return None
    return await Bot.process_event(event_info)
