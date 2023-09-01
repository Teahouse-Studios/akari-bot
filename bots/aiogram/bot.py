import os
import sys

from aiogram import types, executor
from aiogram.types import ContentType

from bots.aiogram.client import dp
from bots.aiogram.info import client_name
from bots.aiogram.message import MessageSession, FetchTarget
from core.builtins import PrivateAssets, Url
from core.parser.message import parser
from core.types import MsgInfo, Session
from core.utils.bot import load_prompt, init_async
from core.utils.info import Info

PrivateAssets.set(os.path.abspath(os.path.dirname(__file__) + '/assets'))
Url.disable_mm = True


@dp.message_handler(content_types=[ContentType.TEXT, ContentType.PHOTO, ContentType.AUDIO])
async def msg_handler(message: types.Message):
    targetId = f'Telegram|{message.chat.type}|{message.chat.id}'
    replyId = None
    if message.reply_to_message is not None:
        replyId = message.reply_to_message.message_id
    msg = MessageSession(MsgInfo(targetId=targetId,
                                 senderId=f'Telegram|User|{message.from_user.id}',
                                 targetFrom=f'Telegram|{message.chat.type}',
                                 senderFrom='Telegram|User', senderName=message.from_user.username,
                                 clientName=client_name,
                                 messageId=message.message_id,
                                 replyId=replyId),
                         Session(message=message, target=message.chat.id, sender=message.from_user.id))
    await parser(msg)


async def on_startup(dispatcher):
    await init_async()
    await load_prompt(FetchTarget)

if 'subprocess' in sys.argv:
    Info.subprocess = True

executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
