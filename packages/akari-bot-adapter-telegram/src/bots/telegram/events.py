from datetime import datetime

from bots.telegram.info import client_name, sender_prefix, target_prefix
from core.builtins.bot import Bot
from core.builtins.session.info import EventInfo


async def member_joined(
    member_id: str | int,
    chat_id: str | int,
    chat_type: str,
    joined_at: datetime | None = None,
    message_id: str | int | None = None,
):
    """将 Telegram 群组成员加入通知转换为核心事件。"""
    target_from = f"{target_prefix}|{chat_type.title()}"
    data = {}
    if joined_at is not None:
        data["joined_at"] = joined_at.isoformat()
    if message_id is not None:
        data["message_id"] = str(message_id)

    event_info = await EventInfo.assign(
        event_name="member_joined",
        target_id=f"{target_from}|{chat_id}",
        target_from=target_from,
        client_name=client_name,
        sender_id=f"{sender_prefix}|{member_id}",
        sender_from=sender_prefix,
        data=data,
    )
    return await Bot.process_event(event_info)


async def handle_new_chat_members(message, bot_id: str | int, ignored_sender: list[str]):
    """逐个分发一条 Telegram 服务消息中包含的新成员。"""
    if message.chat.type not in {"group", "supergroup"}:
        return

    for member in message.new_chat_members or []:
        sender_id = f"{sender_prefix}|{member.id}"
        if member.id == bot_id or sender_id in ignored_sender:
            continue
        await member_joined(
            member.id,
            message.chat.id,
            message.chat.type,
            joined_at=message.date,
            message_id=message.message_id,
        )


async def member_left(
    member_id: str | int,
    chat_id: str | int,
    chat_type: str,
    left_at: datetime | None = None,
    message_id: str | int | None = None,
):
    """将 Telegram 群组成员离开通知转换为核心事件。"""
    target_from = f"{target_prefix}|{chat_type.title()}"
    data = {}
    if left_at is not None:
        data["left_at"] = left_at.isoformat()
    if message_id is not None:
        data["message_id"] = str(message_id)

    event_info = await EventInfo.assign(
        event_name="member_left",
        target_id=f"{target_from}|{chat_id}",
        target_from=target_from,
        client_name=client_name,
        sender_id=f"{sender_prefix}|{member_id}",
        sender_from=sender_prefix,
        data=data,
    )
    return await Bot.process_event(event_info)


async def handle_left_chat_member(message, bot_id: str | int, ignored_sender: list[str]):
    """分发 Telegram 群组成员离开服务消息。"""
    if message.chat.type not in {"group", "supergroup"} or message.left_chat_member is None:
        return

    member = message.left_chat_member
    sender_id = f"{sender_prefix}|{member.id}"
    if member.id == bot_id or sender_id in ignored_sender:
        return
    await member_left(
        member.id,
        message.chat.id,
        message.chat.type,
        left_at=message.date,
        message_id=message.message_id,
    )
