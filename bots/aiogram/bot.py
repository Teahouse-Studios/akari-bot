import os

from aiogram import types, executor

from bots.aiogram.client import dp
from bots.aiogram.message import MessageSession, FetchTarget
from core.elements import MsgInfo, Session, PrivateAssets, Url
from core.parser.message import parser
from core.utils import init, load_prompt, init_async

PrivateAssets.set(os.path.abspath(os.path.dirname(__file__) + '/assets'))
init()
Url.disable_mm = True


@dp.message_handler()
async def msg_handler(message: types.Message):
    targetId = f'Telegram|{message.chat.type}|{message.chat.id}'
    replyId = None
    if message.reply_to_message is not None:
        replyId = message.reply_to_message.message_id
    msg = MessageSession(MsgInfo(targetId=targetId,
                                 senderId=f'Telegram|User|{message.from_user.id}',
                                 targetFrom=f'Telegram|{message.chat.type}',
                                 senderFrom='Telegram|User', senderName=message.from_user.username,
                                 clientName='Telegram',
                                 messageId=message.message_id,
                                 replyId=replyId),
                         Session(message=message, target=message.chat.id, sender=message.from_user.id))
    await parser(msg)


async def on_startup(dispatcher):
    await init_async(FetchTarget)
    await load_prompt(FetchTarget)


if dp:
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
