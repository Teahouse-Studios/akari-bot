import asyncio
import os
import sys

from aiogram import types

from bots.aiogram.client import dp, bot
from bots.aiogram.info import *
from bots.aiogram.message import MessageSession, FetchTarget
from core.bot import load_prompt, init_async
from core.builtins import PrivateAssets, Url
from core.parser.message import parser
from core.path import assets_path
from core.types import MsgInfo, Session
from core.utils.info import Info

PrivateAssets.set(os.path.join(assets_path, 'private', 'aiogram'))
Url.disable_mm = True


@dp.message()
async def msg_handler(message: types.Message):
    target_id = f'{target_name}|{message.chat.type.title()}|{message.chat.id}'
    reply_id = None
    if message.reply_to_message:
        reply_id = message.reply_to_message.message_id
    msg = MessageSession(MsgInfo(target_id=target_id,
                                 sender_id=f'{sender_name}|{message.from_user.id}',
                                 target_from=f'{target_name}|{message.chat.type.title()}',
                                 sender_from=sender_name,
                                 sender_name=message.from_user.username,
                                 client_name=client_name,
                                 message_id=message.message_id,
                                 reply_id=reply_id),
                         Session(message=message, target=message.chat.id, sender=message.from_user.id))
    await parser(msg)


async def on_startup(dispatcher):
    await init_async()
    await load_prompt(FetchTarget)


Info.client_name = client_name
if 'subprocess' in sys.argv:
    Info.subprocess = True

dp.startup.register(on_startup)

asyncio.run(dp.start_polling(bot))
