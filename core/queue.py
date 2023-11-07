import asyncio
from datetime import datetime
import traceback

import ujson as json

from core.builtins import Bot, Temp, MessageChain
from core.logger import Logger
from core.utils.info import get_all_clients_name
from core.utils.ip import append_ip, fetch_ip_info
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

    @classmethod
    async def trigger_hook(cls, target_client: str, module_or_hook_name: str, **kwargs):
        return await cls.add_job(target_client, 'trigger_hook',
                                 {'module_or_hook_name': module_or_hook_name, 'args': kwargs}, wait=False)

    @classmethod
    async def trigger_hook_all(cls, module_or_hook_name: str, **kwargs):
        for target in get_all_clients_name():
            await cls.trigger_hook(target, module_or_hook_name, **kwargs)

    @classmethod
    async def secret_append_ip(cls):
        ip_info = await fetch_ip_info()
        for target in get_all_clients_name():
            await cls.add_job(target, 'secret_append_ip', ip_info, wait=False)

    @classmethod
    async def send_message(cls, target_client: str, target_id: str, message):
        await cls.add_job(target_client, 'send_message', {'target_id': target_id, 'message': message})


def return_val(tsk, value: dict, status=True):
    status = {'status': status}
    if value:
        value = value.update(status)
    else:
        value = status
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
        Logger.debug(f'Args: {args}')
        try:
            if tsk.action == 'validate_permission':
                fetch = await Bot.FetchTarget.fetch_target(args['target_id'], args['sender_id'])
                if fetch:
                    return_val(tsk, {'value': await fetch.parent.check_permission()})
                else:
                    return_val(tsk, {'value': False})
            if tsk.action == 'trigger_hook':
                await Bot.Hook.trigger(args['module_or_hook_name'], args['args'])
                return_val(tsk, {})
            if tsk.action == 'secret_append_ip':
                append_ip(args)
                return_val(tsk, {})
            if tsk.action == 'send_message':
                return_val(tsk, {'send': True})
                try:
                    await Bot.send_message(args['target_id'], MessageChain(args['message']))
                except Exception:
                    Logger.error(traceback.format_exc())
                    return_val(tsk, {'send': False})
            if tsk.action == 'lagrange_keepalive':
                Temp.data['lagrange_keepalive'] = datetime.now().timestamp()
                return_val(tsk, {})
            if tsk.action == 'lagrange_available_groups':
                Temp.data['lagrange_available_groups'] = args
                return_val(tsk, {})

        except Exception as e:
            return_val(tsk, {'traceback': traceback.format_exc()}, status=False)
