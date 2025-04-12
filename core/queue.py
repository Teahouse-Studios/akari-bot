import asyncio
import datetime
import traceback
from uuid import uuid4

from core.builtins import Bot, MessageChain, I18NContext, Plain
from core.config import Config
from core.constants import Info
from core.database.models import JobQueuesTable
from core.logger import Logger
from core.utils.info import get_all_clients_name
from core.utils.ip import append_ip, fetch_ip_info
from core.utils.web_render import check_web_render

_queue_tasks = {}
queue_actions = {}
report_targets = Config("report_targets", [])


class QueueFinished(Exception):
    pass


def action(action_name: str):
    def decorator(func):
        queue_actions[action_name] = func
        return func

    return decorator


class JobQueue:
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
    async def validate_permission(cls, target_client: str, target_id: str, sender_id: str):
        return (await cls.add_job(target_client, "validate_permission",
                                  {"target_id": target_id, "sender_id": sender_id}))["value"]

    @classmethod
    async def trigger_hook(cls, target_client: str, module_or_hook_name: str, **kwargs):
        for k in kwargs:
            if isinstance(kwargs[k], MessageChain):
                kwargs[k] = kwargs[k].to_list()
        return await cls.add_job(target_client, "trigger_hook",
                                 {"module_or_hook_name": module_or_hook_name, "args": kwargs}, wait=False)

    @classmethod
    async def trigger_hook_all(cls, module_or_hook_name: str, **kwargs):
        for target in get_all_clients_name():
            await cls.trigger_hook(target, module_or_hook_name, **kwargs)

    @classmethod
    async def secret_append_ip(cls):
        ip_info = await fetch_ip_info()
        for target in get_all_clients_name():
            await cls.add_job(target, "secret_append_ip", ip_info, wait=False)

    @classmethod
    async def web_render_status(cls):
        web_render_status, web_render_local_status = await check_web_render()
        for target in get_all_clients_name():
            await cls.add_job(target, "web_render_status", {"web_render_status": web_render_status,
                                                            "web_render_local_status": web_render_local_status}, wait=False)

    @classmethod
    async def send_message(cls, target_client: str, target_id: str, message):
        await cls.add_job(target_client, "send_message", {"target_id": target_id, "message": message})


async def return_val(tsk: JobQueuesTable, value: dict, status: str = "done"):
    await tsk.return_val(value, status)
    raise QueueFinished


async def check_job_queue():
    for task_id in _queue_tasks:
        tsk = await JobQueuesTable.get(task_id=task_id)
        if tsk.status == "done":
            _queue_tasks[task_id]["result"] = tsk.result
            _queue_tasks[task_id]["flag"].set()

    get_internal = await JobQueuesTable.get_all(target_client=JobQueue.name)
    get_all = await JobQueuesTable.get_all(target_client=Bot.FetchTarget.name)

    for tsk in get_internal + get_all:
        Logger.debug(f"Received job queue task {tsk.task_id}, action: {tsk.action}")
        Logger.debug(f"Args: {tsk.args}")
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
                    if ft := await Bot.FetchTarget.fetch_target(target):
                        await ft.send_direct_message([I18NContext("error.message.report", module=tsk.action),
                                                      Plain(f.strip(), disable_joke=True)],
                                                     enable_parse_message=False, disable_secret_check=True)
            except Exception:
                Logger.error(traceback.format_exc())


@action("validate_permission")
async def _(tsk: JobQueuesTable, args: dict):
    fetch = await Bot.FetchTarget.fetch_target(args["target_id"], args["sender_id"])
    if fetch:
        await return_val(tsk, {"value": await fetch.parent.check_permission()})
    else:
        await return_val(tsk, {"value": False})


@action("trigger_hook")
async def _(tsk: JobQueuesTable, args: dict):
    await Bot.Hook.trigger(args["module_or_hook_name"], args["args"])
    await return_val(tsk, {})


@action("secret_append_ip")
async def _(tsk: JobQueuesTable, args: dict):
    append_ip(args)
    await return_val(tsk, {})


@action("web_render_status")
async def _(tsk: JobQueuesTable, args: dict):
    Info.web_render_status = args["web_render_status"]
    Info.web_render_local_status = args["web_render_local_status"]
    await return_val(tsk, {})


@action("send_message")
async def _(tsk: JobQueuesTable, args: dict):
    await Bot.send_message(args["target_id"], MessageChain(args["message"]))
    await return_val(tsk, {"send": True})


@action("verify_timezone")
async def _(tsk: JobQueuesTable, args: dict):
    timestamp = tsk.timestamp
    tz_ = datetime.datetime.now().timestamp() - timestamp.timestamp()
    Logger.debug(f"Timezone offset: {tz_}")
    tsk.timestamp = tz_
    await return_val(tsk, {})
