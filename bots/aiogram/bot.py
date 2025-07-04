import asyncio
import sys

from aiogram import types

from bots.aiogram.client import dp, bot
from bots.aiogram.context import AiogramContextManager, AiogramFetchedContextManager
from bots.aiogram.info import *
from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.session.info import SessionInfo
from core.client.init import client_init
from core.config import Config
from core.constants.default import ignored_sender_default
from core.constants.info import Info

Bot.register_bot(client_name=client_name)

ctx_id = Bot.register_context_manager(AiogramContextManager)
Bot.register_context_manager(AiogramFetchedContextManager, fetch_session=True)

ignored_sender = Config("ignored_sender", ignored_sender_default)


@dp.message()
async def msg_handler(message: types.Message):
    target_from = f"{target_prefix}|{message.chat.type.title()}"
    target_id = f"{target_from}|{message.chat.id}"
    sender_id = f"{sender_prefix}|{message.from_user.id}"
    if sender_id in ignored_sender:
        return

    reply_id = None
    if message.reply_to_message:
        reply_id = message.reply_to_message.message_id

    msg_chain = MessageChain.assign(message.text)

    session = await SessionInfo.assign(target_id=target_id,
                                       sender_id=sender_id,
                                       sender_name=message.from_user.username,
                                       target_from=target_from,
                                       sender_from=sender_prefix,
                                       client_name=client_name,
                                       message_id=str(message.message_id),
                                       reply_id=reply_id,
                                       messages=msg_chain,
                                       ctx_slot=ctx_id
                                       )

    await Bot.process_message(session, message)


async def on_startup():
    await client_init(target_prefix_list, sender_prefix_list)


if Config("enable", False, table_name="bot_aiogram"):
    Info.client_name = client_name
    if "subprocess" in sys.argv:
        Info.subprocess = True
    dp.startup.register(on_startup)
    asyncio.run(dp.start_polling(bot))
