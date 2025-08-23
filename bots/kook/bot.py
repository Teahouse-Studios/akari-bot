import asyncio
import re
import sys

from khl import Message, MessageTypes

from bots.kook.client import bot
from bots.kook.context import KOOKContextManager, KOOKFetchedContextManager
from bots.kook.info import *
from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import Plain, Image, Voice
from core.builtins.session.info import SessionInfo
from core.client.init import client_init
from core.config import Config
from core.constants.default import ignored_sender_default

Bot.register_bot(client_name=client_name)

ctx_id = Bot.register_context_manager(KOOKContextManager)
Bot.register_context_manager(KOOKFetchedContextManager, fetch_session=True)

ignored_sender = Config("ignored_sender", ignored_sender_default)
use_url_manager = Config("enable_urlmanager", False)
use_url_md_format = True


async def to_message_chain(message: Message):
    lst = []
    if message.type == MessageTypes.TEXT:
        lst.append(Plain(message.content))
    if message.type == MessageTypes.KMD:
        sub_url = re.sub(r"\[.*?]\((.*?)\)", r"\1", message.content)
        lst.append(Plain(sub_url))
    elif message.type == MessageTypes.IMG:
        lst.append(Image(message.content))
    elif message.type == MessageTypes.AUDIO:
        lst.append(Voice(message.content))
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
        reply_id = message.extra["quote"]["rong_id"]

    msg_chain = await to_message_chain(message)

    session = await SessionInfo.assign(target_id=target_id,
                                       sender_id=sender_id,
                                       sender_name=message.author.nickname,
                                       target_from=f"{target_prefix}|{message.channel_type.name.title()}",
                                       sender_from=sender_prefix,
                                       client_name=client_name,
                                       message_id=str(message.id),
                                       reply_id=reply_id,
                                       messages=msg_chain,
                                       ctx_slot=ctx_id,
                                       use_url_manager=use_url_manager,
                                       use_url_md_format=use_url_md_format,
                                       )

    await Bot.process_message(session, message)


@bot.on_startup
async def _(b: bot):
    await client_init(target_prefix_list, sender_prefix_list)


if Config("enable", False, table_name="bot_kook"):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(bot.start())
