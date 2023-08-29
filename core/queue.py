import asyncio
import traceback

import ujson as json

from core.logger import Logger
from core.builtins import Bot
from database import BotDBUtil


_queue_tasks = {}


class JobQueue:
    @classmethod
    async def add_job(cls, target_client: str, action, args, wait=True):
        taskid = BotDBUtil.JobQueue.add(target_client, action, args)
        if wait:
            flag = asyncio.Event()
            _queue_tasks[taskid] = {'flag': flag}
            await flag.wait()
            result = _queue_tasks[taskid]['result']
            del _queue_tasks[taskid]
            return result
        else:
            return taskid

    @classmethod
    async def validate_permission(cls, target_client: str, target_id: str, sender_id: str):
        return (await cls.add_job(target_client, 'validate_permission',
                                  {'target_id': target_id, 'sender_id': sender_id}))['value']


def return_val(tsk, value: dict, status=True):
    value = value.update({'status': status})
    BotDBUtil.JobQueue.return_val(tsk, value)


async def check_job_queue():
    for tskid in _queue_tasks:
        tsk = BotDBUtil.JobQueue.get(tskid)
        if tsk.hasDone:
            _queue_tasks[tskid]['result'] = json.loads(tsk.returnVal)
            _queue_tasks[tskid]['flag'].set()
    get_all = BotDBUtil.JobQueue.get_all(target_client=Bot.FetchTarget.name)
    for tsk in get_all:
        Logger.debug(f'Received job queue task {tsk.taskid}, action: {tsk.action}')
        args = json.loads(tsk.args)
        try:
            if tsk.action == 'validate_permission':
                fetch = await Bot.FetchTarget.fetch_target(args['target_id'], args['sender_id'])
                if fetch:
                    return_val(tsk, {'value': await fetch.parent.checkPermission()})
        except Exception as e:
            return_val(tsk, {'traceback': traceback.format_exc()}, status=False)
