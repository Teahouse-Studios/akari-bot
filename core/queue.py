import asyncio
import datetime
import traceback
from uuid import uuid4

import orjson as json

from core.builtins import Bot, MessageChain
from core.config import Config
from core.constants import Info, default_locale
from core.database import BotDBUtil
from core.database.tables import JobQueueTable
from core.logger import Logger
from core.utils.i18n import Locale
from core.utils.info import get_all_clients_name
from core.utils.ip import append_ip, fetch_ip_info
from core.utils.web_render import check_web_render

_queue_tasks = {}
queue_actions = {}
report_targets = Config('report_targets', [])


class QueueFinished(Exception):
    pass


def action(action_name: str):
    def decorator(func):
        queue_actions[action_name] = func
        return func

    return decorator


class JobQueue:
    name = 'Internal|' + str(uuid4())

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
        return taskid

    @classmethod
    async def validate_permission(cls, target_client: str, target_id: str, sender_id: str):
        return (await cls.add_job(target_client, 'validate_permission',
                                  {'target_id': target_id, 'sender_id': sender_id}))['value']

    @classmethod
    async def trigger_hook(cls, target_client: str, module_or_hook_name: str, **kwargs):
        for k in kwargs:
            if isinstance(kwargs[k], MessageChain):
                kwargs[k] = kwargs[k].to_list()
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
    async def web_render_status(cls):
        web_render_status, web_render_local_status = await check_web_render()
        for target in get_all_clients_name():
            await cls.add_job(target, 'web_render_status', {'web_render_status': web_render_status,
                                                            'web_render_local_status': web_render_local_status}, wait=False)

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
    raise QueueFinished


async def check_job_queue():
    for tskid in _queue_tasks:
        tsk = BotDBUtil.JobQueue.get(tskid)
        if tsk.hasDone:
            _queue_tasks[tskid]['result'] = json.loads(tsk.returnVal)
            _queue_tasks[tskid]['flag'].set()
    get_internal = BotDBUtil.JobQueue.get_all(target_client=JobQueue.name)
    get_all = BotDBUtil.JobQueue.get_all(target_client=Bot.FetchTarget.name)
    for tsk in get_internal + get_all:
        Logger.debug(f'Received job queue task {tsk.taskid}, action: {tsk.action}')
        args = json.loads(tsk.args)
        Logger.debug(f'Args: {args}')
        try:
            timestamp = tsk.timestamp
            if BotDBUtil.time_offset is not None and datetime.datetime.now().timestamp() - timestamp.timestamp() - \
                    BotDBUtil.time_offset > 7200:
                Logger.warning(f'Task {tsk.taskid} timeout, {
                    datetime.datetime.now().timestamp() - timestamp.timestamp() - BotDBUtil.time_offset}, skip.')
            elif tsk.action in queue_actions:
                await queue_actions[tsk.action](tsk, args)
                Logger.warning(f'Task {tsk.action}({tsk.taskid}) not returned any value, did you forgot something?')
            else:
                Logger.warning(f'Unknown action {tsk.action}, skip.')
            return_val(tsk, {}, status=False)
        except QueueFinished:
            Logger.debug(f'Task {tsk.action}({tsk.taskid}) finished.')
        except Exception:
            f = traceback.format_exc()
            Logger.error(f)
            try:
                return_val(tsk, {'traceback': f}, status=False)
            except QueueFinished:
                pass
            try:
                for target in report_targets:
                    if ft := await Bot.FetchTarget.fetch_target(target):
                        await ft.send_direct_message(
                            Locale(default_locale).t('error.message.report', module=tsk.action, detail=f),
                            enable_parse_message=False, disable_secret_check=True)
            except Exception:
                Logger.error(traceback.format_exc())


@action('validate_permission')
async def _(tsk: JobQueueTable, args: dict):
    fetch = await Bot.FetchTarget.fetch_target(args['target_id'], args['sender_id'])
    if fetch:
        return_val(tsk, {'value': await fetch.parent.check_permission()})
    else:
        return_val(tsk, {'value': False})


@action('trigger_hook')
async def _(tsk: JobQueueTable, args: dict):
    await Bot.Hook.trigger(args['module_or_hook_name'], args['args'])
    return_val(tsk, {})


@action('secret_append_ip')
async def _(tsk: JobQueueTable, args: dict):
    append_ip(args)
    return_val(tsk, {})


@action('web_render_status')
async def _(tsk: JobQueueTable, args: dict):
    Info.web_render_status = args['web_render_status']
    Info.web_render_local_status = args['web_render_local_status']
    return_val(tsk, {})


@action('send_message')
async def _(tsk: JobQueueTable, args: dict):
    await Bot.send_message(args['target_id'], MessageChain(args['message']))
    return_val(tsk, {'send': True})


@action('verify_timezone')
async def _(tsk: JobQueueTable, args: dict):
    timestamp = tsk.timestamp
    tz_ = datetime.datetime.now().timestamp() - timestamp.timestamp()
    Logger.debug(f'Timezone offset: {tz_}')
    BotDBUtil.time_offset = tz_
    return_val(tsk, {})
