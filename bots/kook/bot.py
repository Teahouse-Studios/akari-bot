import re

from khl import Bot as khlBot, EventTypes, Event, Message, MessageTypes

from bots.kook.client import bot
from bots.kook.config import KookConfig
from bots.kook.context import KOOKContextManager, KOOKFetchedContextManager, KOOKReactionContext
from bots.kook.events import guild_member_joined, guild_member_left
from bots.kook.info import *
from bots.kook.lifecycle import run_bot
from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import Plain, Image, Audio, Video
from core.builtins.session.info import SessionInfo
from core.builtins.utils import command_prefix
from core.client.init import client_init
from core.config.base import CoreConfig

Bot.register_bot(client_name=client_name)

ctx_id = Bot.register_context_manager(KOOKContextManager)
Bot.register_context_manager(KOOKFetchedContextManager, fetch_session=True)

ignored_sender = CoreConfig.ignored_sender
mention_required = CoreConfig.mention_required


async def to_message_chain(message: Message):
    lst = []
    if message.type == MessageTypes.TEXT:
        lst.append(Plain(message.content))
    if message.type == MessageTypes.KMD:
        message.content = re.sub(r"\[.*?]\((.*?)\)", r"\1", message.content)
        message.content = re.sub(r"\(met\)(.*?)\(met\)", rf"{sender_prefix}|\1", message.content)
        lst.append(Plain(message.content))
    elif message.type == MessageTypes.IMG:
        lst.append(Image(message.content))
    elif message.type == MessageTypes.AUDIO:
        lst.append(Audio(message.content))
    elif message.type == MessageTypes.VIDEO:
        lst.append(Video(message.content))
    return MessageChain.assign(lst)


@bot.on_message((MessageTypes.TEXT, MessageTypes.IMG))
async def msg_handler(message: Message):
    if message.channel_type.name == "GROUP":
        target_id = f"{target_group_prefix}|{message.target_id}"
    else:
        target_id = f"{target_person_prefix}|{message.author_id}"
    sender_id = f"{sender_prefix}|{message.author_id}"
    if sender_id in ignored_sender:
        return

    reply_id = None
    if "quote" in message.extra:
        reply_id = message.extra.get("quote", {}).get("rong_id")

    at_message = False
    match_at = re.match(r"^\(met\)(\d+)\(met\)", message.content)
    if match_at:
        mention_id = match_at.group(1)
        if mention_id == str(bot.me.id):
            at_message = True
            message.content = re.sub(r"^\(met\)\d+\(met\)", "", message.content).strip()
            if not message.content:
                message.content = f"{command_prefix[0]}help"
        else:
            return
    if mention_required and not at_message and message.channel_type.name == "GROUP":
        return

    msg_chain = await to_message_chain(message)

    session = await SessionInfo.assign(
        target_id=target_id,
        sender_id=sender_id,
        sender_name=message.author.nickname,
        target_from=f"{target_prefix}|{message.channel_type.name.title()}",
        is_private=message.channel_type.name.title() == "Person",
        sender_from=sender_prefix,
        client_name=client_name,
        message_id=str(message.id),
        reply_id=reply_id,
        messages=msg_chain,
        ctx_slot=ctx_id,
        bot_id=bot.me.id,
    )

    await Bot.process_message(session, message)


@bot.on_event(EventTypes.ADDED_REACTION)
async def add_reaction(b: khlBot, event: Event):
    body = event.extra.get("body", {})
    user_id = body.get("user_id")
    channel_id = body.get("channel_id")
    origin_message_id = body.get("msg_id")
    emoji = body.get("emoji", {}).get("id")
    if user_id is None or channel_id is None or origin_message_id is None or not emoji:
        return
    user_id = str(user_id)
    if user_id == str(b.client.me.id):
        return
    sender_id = f"{sender_prefix}|{user_id}"
    if sender_id in ignored_sender:
        return

    origin_message_id = str(origin_message_id)
    emoji = str(emoji)
    context = KOOKReactionContext(
        origin_message_id=origin_message_id,
        emoji=emoji,
        user_id=user_id,
    )
    session = await SessionInfo.assign(
        target_id=f"{target_group_prefix}|{channel_id}",
        sender_id=sender_id,
        target_from=target_group_prefix,
        sender_from=sender_prefix,
        client_name=client_name,
        message_id=str(event.id) if event.id is not None else None,
        reply_id=origin_message_id,
        messages=MessageChain.assign([Plain(emoji)]),
        ctx_slot=ctx_id,
        bot_id=bot.me.id,
    )

    await Bot.process_message(session, context)


@bot.on_event(EventTypes.PRIVATE_ADDED_REACTION)
async def private_add_reaction(b: khlBot, event: Event):
    body = event.extra.get("body", {})
    user_id = body.get("user_id")
    origin_message_id = body.get("msg_id")
    emoji = body.get("emoji", {}).get("id")
    if user_id is None or origin_message_id is None or not emoji:
        return
    user_id = str(user_id)
    if user_id == str(b.client.me.id):
        return
    sender_id = f"{sender_prefix}|{user_id}"
    if sender_id in ignored_sender:
        return

    origin_message_id = str(origin_message_id)
    emoji = str(emoji)
    context = KOOKReactionContext(
        origin_message_id=origin_message_id,
        emoji=emoji,
        user_id=user_id,
    )
    session = await SessionInfo.assign(
        target_id=f"{target_person_prefix}|{user_id}",
        sender_id=sender_id,
        target_from=target_person_prefix,
        is_private=True,
        sender_from=sender_prefix,
        client_name=client_name,
        message_id=str(event.id) if event.id is not None else None,
        reply_id=origin_message_id,
        messages=MessageChain.assign([Plain(emoji)]),
        ctx_slot=ctx_id,
        bot_id=bot.me.id,
    )

    await Bot.process_message(session, context)


@bot.on_event(EventTypes.JOINED_GUILD)
async def joined_guild(b: khlBot, event: Event):
    """接收 KOOK 服务器成员加入事件。"""
    body = event.body
    member_id = body.get("user_id")
    guild_id = event.target_id
    if not member_id or not guild_id:
        return

    sender_id = f"{sender_prefix}|{member_id}"
    if member_id == b.client.me.id or sender_id in ignored_sender:
        return

    await guild_member_joined(
        member_id,
        guild_id,
        joined_at=body.get("joined_at"),
        event_id=str(event.id) if event.id is not None else None,
    )


@bot.on_event(EventTypes.EXITED_GUILD)
async def exited_guild(b: khlBot, event: Event):
    """接收 KOOK 服务器成员离开事件。"""
    body = event.body
    member_id = body.get("user_id")
    guild_id = event.target_id
    if not member_id or not guild_id:
        return

    sender_id = f"{sender_prefix}|{member_id}"
    if member_id == b.client.me.id or sender_id in ignored_sender:
        return

    await guild_member_left(
        member_id,
        guild_id,
        left_at=body.get("exited_at"),
        event_id=str(event.id) if event.id is not None else None,
    )


@bot.on_startup
async def _(b: khlBot):
    await client_init(target_prefix_list, sender_prefix_list)


if KookConfig.enable:
    run_bot(bot)
