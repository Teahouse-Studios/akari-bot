"""
服务器清理和重启模块。

负责服务器的关闭和重启，包括：
- 会话清理
- 任务队列清空
- 调度器关闭
- 数据库连接关闭
"""

import asyncio
import os

import orjson
from apscheduler.schedulers import SchedulerNotRunningError
from tortoise import Tortoise

# from core.builtins.session.tasks import SessionTaskManager
from core.alive import Alive
from core.builtins.converter import converter
from core.builtins.session.features import Features
from core.constants import PrivateAssets
from core.database.models import JobQueuesTable
from core.logger import Logger
from core.restart import RESTART_ALL_EXIT_CODE, RESTART_PROCESS_EXIT_CODE, get_bot_client_name
from core.scheduler import Scheduler
from core.web_render import close_web_render


async def cleanup_sessions() -> bool:
    """清理服务器资源。

    执行以下清理步骤：
    1. 关闭调度器和 WebRender
    2. 最终清空任务队列
    3. 关闭数据库连接
    """
    cleanup_ok = True
    # get_wait_list = SessionTaskManager.get()
    Logger.warning("Cleaning up sessions...")
    # for x in get_wait_list:
    #     for y in get_wait_list[x]:
    #         for z in get_wait_list[x][y]:
    #             if get_wait_list[x][y][z]["active"]:
    #                 await z.send_message(I18NContext("core.message.restart.prompt"))
    try:
        Scheduler.shutdown()
    except SchedulerNotRunningError:
        pass
    except Exception:
        cleanup_ok = False
        Logger.exception("Failed to stop scheduler cleanly.")
    try:
        await asyncio.wait_for(close_web_render(), timeout=10)
    except TimeoutError:
        cleanup_ok = False
        Logger.warning("Timed out while closing WebRender.")
    except Exception:
        cleanup_ok = False
        Logger.exception("Failed to close WebRender cleanly.")
    # 所有队列生产者停止后再执行最终清表，避免 worker/Scheduler 在清理后重新写入。
    if Tortoise._inited:
        try:
            await JobQueuesTable.clear_all_tasks()
        except Exception:
            cleanup_ok = False
            Logger.exception("Failed to clear job queues cleanly.")
    try:
        await Tortoise.close_connections()
    except Exception:
        cleanup_ok = False
        Logger.exception("Failed to close database connections cleanly.")
    return cleanup_ok


def cache_alive_clients() -> None:
    """为 server-only 重启保存客户端路由信息。"""
    alive_cache = PrivateAssets.path / ".cache_restart_alive"
    values = {}
    for client_name, data in Alive.get_alive().items():
        features = data.get("features")
        values[client_name] = {
            "target_prefix_list": data.get("target_prefix_list") or [],
            "sender_prefix_list": data.get("sender_prefix_list") or [],
            "ctx_slot_index": data.get("ctx_slot_index"),
            "features": converter.unstructure(features, Features) if features else None,
        }
    alive_cache.write_bytes(orjson.dumps(values))


async def restart(server_only: bool = False):
    """重启服务器。

    执行清理后强制退出并发出自定义状态码，上级进程会自动重启服务。
    """
    if server_only:
        try:
            cache_alive_clients()
        except Exception:
            Logger.exception("Failed to cache alive clients before restarting Server.")
    # restart() 本身运行在一个 JobQueue worker 内；保留当前 worker，先收束其他 worker 和轮询器，
    # 防止 cleanup_sessions() 最终清表后仍有并发任务写回。
    from core.queue.server import JobQueueServer

    await JobQueueServer.shutdown_workers()
    await cleanup_sessions()
    os._exit(RESTART_PROCESS_EXIT_CODE if server_only else RESTART_ALL_EXIT_CODE)


async def restart_bots(bot_names: tuple[str, ...]) -> tuple[str, ...]:
    """通知指定平台客户端自行退出，由守护进程单独拉起。

    返回无法映射或当前不在线的平台目录名。bot-only 路径不会清理 server
    会话，也不会写 server 重启提示缓存。
    """
    from core.queue.server import JobQueueServer

    async def request_restart(bot_name: str) -> str | None:
        client_name = get_bot_client_name(bot_name)
        if not client_name:
            return bot_name
        task_id = await JobQueueServer.add_job(client_name, "restart_client", {}, wait=False)
        if not task_id:
            return bot_name
        for _ in range(50):
            task = await JobQueuesTable.get_or_none(task_id=task_id)
            if task and task.status == "done":
                return None
            if task and task.status in {"failed", "timeout"}:
                break
            await asyncio.sleep(0.1)
        await JobQueuesTable.filter(task_id=task_id, status__in=["pending", "processing"]).delete()
        return bot_name

    results = await asyncio.gather(*(request_restart(bot_name) for bot_name in bot_names))
    return tuple(bot_name for bot_name in results if bot_name)
