import asyncio
import datetime
import traceback
from typing import TYPE_CHECKING, Union
from uuid import uuid4

from core.builtins.converter import converter
from core.builtins.message.chain import MessageChain, MessageNodes
from core.builtins.message.internal import I18NContext, Plain
from core.builtins.session.info import SessionInfo
from core.config import Config
from core.constants import QueueAlreadyRunning
from core.database.models import JobQueuesTable
from core.exports import exports
from core.logger import Logger

if TYPE_CHECKING:
    from core.builtins.bot import Bot


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
    is_running = False

    @classmethod
    async def add_job(cls, target_client: str, action, args, wait=True):
        if target_client:
            task_id = await JobQueuesTable.add_task(target_client, action, args)
        else:
            Logger.warning(f"Cannot add job {action} due to target_client is None, perhaps a bug?")
            return None
        if wait:
            return await QueueTaskManager.add(task_id)
        return task_id

    @staticmethod
    async def return_val(tsk: JobQueuesTable, value: dict, status: str = "done"):
        await tsk.set_val(value, status)
        raise QueueFinished

    @classmethod
    async def _process_task(cls, tsk):
        bot: "Bot" = exports["Bot"]
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
            Logger.trace(f"Task {tsk.action}({tsk.task_id}) finished.")
            return
        except Exception:
            f = traceback.format_exc()
            Logger.error(f)
            try:
                await cls.return_val(tsk, {"traceback": f}, status="failed")
            except QueueFinished:
                pass
            try:
                for target in cls.report_targets:
                    if ft := await bot.fetch_target(target):
                        await cls.client_direct_message(ft, MessageChain.assign(
                            [I18NContext("error.message.report", command=tsk.action),
                             Plain(f.strip(), disable_joke=True)]), enable_parse_message=False,
                            disable_secret_check=True)
            except Exception:
                Logger.exception()
            return

        # The code below should not be reached if the task is processed correctly.
        Logger.error(f"Task {tsk.action}({tsk.task_id}) seems not finished properly, bug in code?")
        await tsk.set_status("failed")

    @classmethod
    async def _check_queue(cls, target_client: str = None):
        # Logger.debug(f"Checking job queue for {cls.name}, target client: {target_client if target_client else "all"}")
        for task_id in QueueTaskManager.tasks.copy():
            tsk = await JobQueuesTable.get_or_none(task_id=task_id)
            if tsk and tsk.status not in ["pending", "processing"]:
                await QueueTaskManager.set_result(task_id, tsk.result)
        # Logger.debug([cls.name, target_client if target_client else exports["Bot"].Info.client_name])

        get_all = await JobQueuesTable.get_all(
            [cls.name, target_client if target_client else exports["Bot"].Info.client_name])

        for tsk in get_all:
            Logger.trace(f"Received job queue task {tsk.task_id}, action: {tsk.action}")
            Logger.trace(f"Args: {tsk.args}")
            await tsk.set_status("processing")
            asyncio.create_task(cls._process_task(tsk))

    @classmethod
    async def check_job_queue(cls, target_client: str = None):
        if cls.is_running:
            raise QueueAlreadyRunning
        cls.is_running = True
        while True:
            await cls._check_queue(target_client)
            await asyncio.sleep(0.1)

    @classmethod
    def action(cls, action_name: str):
        def decorator(func):
            cls.queue_actions[action_name] = func
            return func

        return decorator

    @classmethod
    async def client_direct_message(cls, session_info: SessionInfo, message: MessageChain | MessageNodes,
                                    enable_parse_message=False, disable_secret_check=True):
        await cls.add_job("Server", "client_direct_message",
                          {"session_info": converter.unstructure(session_info),
                           "message": converter.unstructure(message, Union[MessageChain, MessageNodes]),
                           "enable_parse_message": enable_parse_message,
                           "disable_secret_check": disable_secret_check}, )
