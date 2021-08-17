from aiogram.dispatcher.filters import Command
from aiogram.types import ChatType

from core.bots.aiogram.client import dp
from aiogram import types, executor
from core.bots.aiogram.message import MessageSession
from core.elements import MsgInfo, Session
from core.elements.others import confirm_command
from core.parser.message import parser
from core.bots.aiogram.tasks import MessageTaskManager, FinishedTasks


@dp.message_handler()
async def msg_handler(message: types.Message):
    all_tsk = MessageTaskManager.get()
    user_id = message.from_user.id
    if user_id in all_tsk:
        FinishedTasks.add_task(user_id, message)
        all_tsk[user_id].set()
        MessageTaskManager.del_task(user_id)
        return
    msg = MessageSession(MsgInfo(targetId=f'Telegram|{message.chat.type}|{message.chat.id}',
                                 senderId=f'Telegram|User|{message.from_user.id}', targetFrom='Telegram',
                                 senderFrom='Telegram', senderName=message.from_user.username),
                         Session(message=message, target=message.chat, sender=message.from_user))
    await parser(msg)

if dp:
    executor.start_polling(dp, skip_updates=True)
