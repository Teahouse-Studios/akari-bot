from datetime import datetime

from bots.discord.info import client_name, sender_prefix, target_guild_prefix
from core.builtins.bot import Bot
from core.builtins.session.info import EventInfo


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
