import asyncio
import logging
import os

from core.bots.aiocqhttp.client import bot
from core.bots.aiocqhttp.message import MessageSession, FetchTarget
from core.bots.aiocqhttp.tasks import MessageTaskManager, FinishedTasks
from aiocqhttp import Event

from core.elements import MsgInfo, Session, StartUp, Schedule, EnableDirtyWordCheck
from core.loader import Modules
from core.parser.message import parser
from core.scheduler import Scheduler
from core.utils import PrivateAssets, init, load_prompt

PrivateAssets.set(os.path.abspath(os.path.dirname(__file__) + '/assets'))
EnableDirtyWordCheck.status = True
init()


@bot.on_startup
async def startup():
    gather_list = []
    for x in Modules:
        if isinstance(Modules[x], StartUp):
            gather_list.append(asyncio.ensure_future(Modules[x].function(FetchTarget)))
        elif isinstance(Modules[x], Schedule):
            Scheduler.add_job(func=Modules[x].function, trigger=Modules[x].trigger, args=[FetchTarget])
    await asyncio.gather(*gather_list)
    Scheduler.start()
    logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)
    bot.logger.setLevel(logging.WARNING)
    await load_prompt(FetchTarget)


@bot.on_message
async def _(event: Event):
    all_tsk = MessageTaskManager.get()
    user_id = event.user_id
    if user_id in all_tsk:
        FinishedTasks.add_task(user_id, event.message)
        all_tsk[user_id].set()
        MessageTaskManager.del_task(user_id)
    targetId = 'QQ|' + (f'Group|{str(event.group_id)}' if event.detail_type == 'group' else str(event.user_id))
    msg = MessageSession(MsgInfo(targetId=targetId,
                                 senderId=f'QQ|{str(event.user_id)}',
                                 targetFrom='QQ|Group' if event.detail_type == 'group' else 'QQ',
                                 senderFrom='QQ', senderName=''), Session(message=event,
                                                                          target=event.group_id if event.detail_type == 'group' else event.user_id,
                                                                          sender=event.user_id))
    await parser(msg)


@bot.on('request.friend')
async def _(event: Event):
    return {'approve': True}


bot.run(host='127.0.0.1', port=11901, debug=False)
