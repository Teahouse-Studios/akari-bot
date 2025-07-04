import asyncio
import os
import sys

from aiogram import types

sys.path.append(os.getcwd())

from bots.aiogram.client import dp, bot  # noqa: E402
from bots.aiogram.info import *  # noqa: E402
from bots.aiogram.message import MessageSession, FetchTarget  # noqa: E402
from core.server.init import load_prompt, init_async  # noqa: E402
from core.constants import PrivateAssets  # noqa: E402
from core.config import Config  # noqa: E402
from core.constants.default import ignored_sender_default  # noqa: E402
from core.constants.path import assets_path  # noqa: E402
from core.builtins.parser.message import parser  # noqa: E402

PrivateAssets.set(os.path.join(assets_path, "private", "aiogram"))
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

    msg = MessageSession(
        MsgInfo(
            target_id=target_id,
            sender_id=sender_id,
            target_from=target_from,
            sender_from=sender_prefix,
            sender_name=message.from_user.username,
            client_name=client_name,
            message_id=message.message_id,
            reply_id=reply_id,
        ),
        Session(message=message, target=message.chat.id, sender=message.from_user.id),
    )
    await parser(msg)


async def on_startup():
    await init_async()
    await load_prompt(FetchTarget)


async def on_shutdown():
    await cleanup_sessions()


if Config("enable", False, table_name="bot_aiogram") or __name__ == "__main__":
    Info.client_name = client_name
    if "subprocess" in sys.argv:
        Info.subprocess = True

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    asyncio.run(dp.start_polling(bot))
