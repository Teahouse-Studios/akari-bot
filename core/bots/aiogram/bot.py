from aiogram.dispatcher.filters import Command
from aiogram.types import ChatType

from core.bots.aiogram.client import dp
from aiogram import types, executor
from core.bots.aiogram.message import MessageSession
from core.elements import MsgInfo, Session
from core.parser.message import parser


@dp.message_handler()
async def msg_handler(message: types.Message):
    msg = MessageSession(MsgInfo(targetId=f'Telegram|{message.chat.type}|{message.chat.id}',
                                 senderId=f'Telegram|User|{message.from_user.id}', targetFrom='Telegram',
                                 senderFrom='Telegram', senderName=message.from_user.username),
                         Session(message=message, target=message.chat, sender=message.from_user))
    await parser(msg)

@dp.chat_member_handler()
async def msg_handler(message: types.Message):
    print(message)

if dp:
    executor.start_polling(dp, skip_updates=True)