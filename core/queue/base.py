import asyncio
import datetime
import traceback
from uuid import uuid4

from core.config import Config
from core.database.models import JobQueuesTable
from core.logger import Logger
from core.utils.info import get_all_clients_name
from core.exports import exports

_queue_tasks = {}
queue_actions = {}
report_targets = Config("report_targets", [])


class QueueFinished(Exception):
    pass


class JobQueueBase:
    name = "Internal|" + str(uuid4())

    @classmethod
    async def add_job(cls, target_client: str, action, args, wait=True):
        task_id = await JobQueuesTable.add_task(target_client, action, args)
        if wait:
            flag = asyncio.Event()
            _queue_tasks[task_id] = {"flag": flag}
            await flag.wait()
            result = _queue_tasks[task_id]["result"]
            del _queue_tasks[task_id]
            return result
        return task_id

    @classmethod
    async def trigger_hook(cls, target_client: str, module_or_hook_name: str, **kwargs):
        for k in kwargs:
            if isinstance(kwargs[k], exports["MessageChain"]):
                kwargs[k] = kwargs[k].to_list()
        return await cls.add_job(target_client, "trigger_hook",
                                 {"module_or_hook_name": module_or_hook_name, "args": kwargs}, wait=False)

    @classmethod
    async def trigger_hook_all(cls, module_or_hook_name: str, **kwargs):
        for target in get_all_clients_name():
            await cls.trigger_hook(target, module_or_hook_name, **kwargs)

    @staticmethod
    async def return_val(tsk: JobQueuesTable, value: dict, status: str = "done"):
        await tsk.return_val(value, status)
        raise QueueFinished

    @classmethod
    async def check_job_queue(cls, target_client: str = None):
        for task_id in _queue_tasks:
            tsk = await JobQueuesTable.get(task_id=task_id)
            if tsk.status == "done":
                _queue_tasks[task_id]["result"] = tsk.result
                _queue_tasks[task_id]["flag"].set()

        get_internal = await JobQueuesTable.get_all(target_client=cls.name)
        get_all = await JobQueuesTable.get_all(target_client=target_client if target_client else exports['Bot'].FetchTarget.name)

        for tsk in get_internal + get_all:
            Logger.debug(f"Received job queue task {tsk.task_id}, action: {tsk.action}")
            Logger.debug(f"Args: {tsk.args}")
            await tsk.set_status('processing')
            try:
                timestamp = tsk.timestamp
                if datetime.datetime.now().timestamp() - timestamp.timestamp() > 7200:
                    Logger.warning(f"Task {tsk.task_id} timeout, skip.")
                    await tsk.return_val({}, status="timeout")
                elif tsk.action in queue_actions:
                    await queue_actions[tsk.action](tsk, tsk.args)
                else:
                    Logger.warning(f"Unknown action {tsk.action}, skip.")
                    await tsk.return_val({}, status="failed")
            except QueueFinished:
                Logger.debug(f"Task {tsk.action}({tsk.task_id}) finished.")
            except Exception:
                f = traceback.format_exc()
                Logger.error(f)
                try:
                    await tsk.return_val({"traceback": f}, status="failed")
                except QueueFinished:
                    pass
                try:
                    for target in report_targets:
                        if ft := await exports['Bot'].FetchTarget.fetch_target(target):
                            await ft.send_direct_message([exports["I18NContext"]("error.message.report", module=tsk.action),
                                                          exports["Plain"](f.strip(), disable_joke=True)],
                                                         enable_parse_message=False, disable_secret_check=True)
                except Exception:
                    Logger.error(traceback.format_exc())

    @staticmethod
    def action(action_name: str):
        def decorator(func):
            queue_actions[action_name] = func
            return func

        return decorator
