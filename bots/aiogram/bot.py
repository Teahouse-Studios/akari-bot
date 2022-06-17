import os

from aiogram import types, executor

from bots.aiogram.client import dp
from bots.aiogram.message import MessageSession, FetchTarget
from bots.aiogram.tasks import MessageTaskManager, FinishedTasks
from core.elements import MsgInfo, Session, PrivateAssets, Url
from core.parser.message import parser
from core.utils import init, load_prompt, init_async

PrivateAssets.set(os.path.abspath(os.path.dirname(__file__) + '/assets'))
init()
Url.disable_mm = True


@dp.message_handler()
async def msg_handler(message: types.Message):
    all_tsk = MessageTaskManager.get()
    user_id = message.from_user.id
    targetId = f'Telegram|{message.chat.type}|{message.chat.id}'
    if targetId in all_tsk:
        if user_id in all_tsk[targetId]:
            FinishedTasks.add_task(targetId, user_id, message)
            all_tsk[targetId][user_id].set()
            MessageTaskManager.del_task(targetId, user_id)
    msg = MessageSession(MsgInfo(targetId=targetId,
                                 senderId=f'Telegram|User|{message.from_user.id}',
                                 targetFrom=f'Telegram|{message.chat.type}',
                                 senderFrom='Telegram|User', senderName=message.from_user.username, clientName='Telegram'),
                         Session(message=message, target=message.chat.id, sender=message.from_user.id))
    await parser(msg)


async def on_startup(dispatcher):
    await init_async(FetchTarget)
    await load_prompt(FetchTarget)


if dp:
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
