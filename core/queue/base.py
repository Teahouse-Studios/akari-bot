import asyncio
import datetime
import traceback
from uuid import uuid4

from core.config import Config
from core.database.models import JobQueuesTable
from core.logger import Logger
from core.utils.info import get_all_clients_name
from core.exports import exports
from core.utils.templist import TempList


class QueueFinished(Exception):
    pass


class QueueTaskManager:
    tasks = {}

    @classmethod
    async def add(cls, task_id: str):
        try:
            cls.tasks[task_id] = {"flag": asyncio.Event()}
            await cls.tasks[task_id]["flag"].wait()
            return cls.tasks[task_id]["result"]
        except Exception as e:
            Logger.error(f"Error in QueueTaskManager: {e}")
            return None
        finally:
            if task_id in cls.tasks:
                del cls.tasks[task_id]

    @classmethod
    async def set_result(cls, task_id: str, result: dict):
        if task_id in cls.tasks:
            cls.tasks[task_id]["result"] = result
            cls.tasks[task_id]["flag"].set()


class JobQueueBase:
    name = "Internal|" + str(uuid4())
    _queue_tasks = {}
    queue_actions = {}
    report_targets = Config("report_targets", [])

    @classmethod
    async def add_job(cls, target_client: str, action, args, wait=True):
        task_id = await JobQueuesTable.add_task(target_client, action, args)
        if wait:
            return await QueueTaskManager.add(task_id)
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
    async def _process_task(cls, tsk):

        try:
            timestamp = tsk.timestamp
            if datetime.datetime.now().timestamp() - timestamp.timestamp() > 7200:
                Logger.warning(f"Task {tsk.task_id} timeout, skip.")
                await cls.return_val(tsk, {}, status="timeout")
            elif tsk.action in cls.queue_actions:
                returns: dict = await cls.queue_actions[tsk.action](tsk, tsk.args)
                await cls.return_val(tsk, returns if returns else {}, status="done")
            else:
                Logger.warning(f"Unknown action {tsk.action}, skip.")
                await cls.return_val(tsk, {}, status="failed")
        except QueueFinished:
            Logger.debug(f"Task {tsk.action}({tsk.task_id}) finished.")
        except Exception:
            f = traceback.format_exc()
            Logger.error(f)
            try:
                await cls.return_val(tsk, {"traceback": f}, status="failed")
            except QueueFinished:
                pass
            try:
                for target in cls.report_targets:
                    if ft := await exports['Bot'].fetch_target(target):
                        await ft.send_direct_message([exports["I18NContext"]("error.message.report", module=tsk.action),
                                                      exports["Plain"](f.strip(), disable_joke=True)],
                                                     enable_parse_message=False, disable_secret_check=True)
            except Exception:
                Logger.error(traceback.format_exc())

    @classmethod
    async def check_job_queue(cls, target_client: str = None):
        # Logger.debug(f"Checking job queue for {cls.name}, target client: {target_client if target_client else 'all'}")
        for task_id in QueueTaskManager.tasks.copy():
            tsk = await JobQueuesTable.get(task_id=task_id)
            if tsk.status == "done":
                await QueueTaskManager.set_result(task_id, tsk.result)
        # Logger.debug([cls.name, target_client if target_client else exports['Bot'].Info.client_name])

        get_all = await JobQueuesTable.get_all([cls.name, target_client if target_client else exports['Bot'].Info.client_name])

        for tsk in get_all:
            Logger.debug(f"Received job queue task {tsk.task_id}, action: {tsk.action}")
            Logger.debug(f"Args: {tsk.args}")
            await tsk.set_status('processing')
            asyncio.create_task(cls._process_task(tsk))

    @classmethod
    def action(cls, action_name: str):
        def decorator(func):
            cls.queue_actions[action_name] = func
            return func

        return decorator
