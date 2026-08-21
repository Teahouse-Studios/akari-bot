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
import sys

from tortoise import Tortoise

# from core.builtins.session.tasks import SessionTaskManager
from core.database.models import JobQueuesTable
from core.logger import Logger
from core.queue.server import JobQueueServer
from core.scheduler import SchedulerLifecycle
from core.web_render import close_web_render
from .background_tasks import stop_background_task


async def _cancel_loaded_background_tasks(module_name: str, function_name: str, label: str) -> None:
    """取消一个已加载模块持有的后台任务，不在关闭阶段额外导入模块。"""
    module = sys.modules.get(module_name)
    cancel = getattr(module, function_name, None) if module else None
    if cancel is None:
        return
    try:
        await asyncio.wait_for(cancel(), timeout=10)
    except TimeoutError:
        Logger.warning(f"Timed out while cancelling {label} background tasks.")
    except Exception:
        Logger.exception(f"Failed to cancel {label} background tasks cleanly.")


async def cleanup_sessions():
    """清理服务器资源。

    执行以下清理步骤：
    1. 清理所有待处理的任务队列
    2. 关闭调度器
    3. 关闭数据库连接
    """
    # get_wait_list = SessionTaskManager.get()
    Logger.warning("Cleaning up sessions...")
    # for x in get_wait_list:
    #     for y in get_wait_list[x]:
    #         for z in get_wait_list[x][y]:
    #             if get_wait_list[x][y][z]["active"]:
    #                 await z.send_message(I18NContext("core.message.restart.prompt"))
    # 先同步关闭 Scheduler 的新任务入口；真正取消／等待运行中 Job 放在 Queue
    # shutdown_window 内、其它 Queue handler 已取消之后执行，避免正在 reload_db 的
    # handler 持有 Scheduler 维护锁时与 restart action 互相等待。
    SchedulerLifecycle.begin_shutdown()
    try:
        await stop_background_task()
    except Exception:
        Logger.exception("Failed to stop background initialization cleanly.")
    # 这些任务持有 MessageSession context，取消时会经 JobQueue 请求平台进程 release。
    # 因此必须在停止 Server queue poller 之前执行；关闭阶段只处理已经加载的模块，
    # 不能为了清理而导入一个本来没有启用的模块及其数据库／配置依赖。
    await _cancel_loaded_background_tasks(
        "modules.wiki.wiki",
        "cancel_wiki_background_tasks",
        "Wiki",
    )
    await _cancel_loaded_background_tasks(
        "modules.core.bind",
        "cancel_bind_handshake_tasks",
        "bind handshake",
    )
    await _cancel_loaded_background_tasks(
        "core.retired",
        "cancel_retired_notice_tasks",
        "retired notice",
    )
    # restart() 可能由 Queue action 自身触发，此时主循环的轮询器仍在运行。关闭窗口
    # 必须先阻止它继续领取任务，再取消其它 handler，并在独占轮询锁时清库、关资源；
    # 否则清空队列或关闭连接期间仍可能启动一个新的平台副作用。
    async with JobQueueServer.shutdown_window():
        try:
            await SchedulerLifecycle.shutdown()
        except Exception:
            Logger.exception("Failed to stop scheduler cleanly.")
        # detached task 的 context 已经释放，此后不再需要轮询远端结果。先停止轮询器，
        # 再在持有 _poll_lock 的情况下清库和关连接，避免窗口退出后轮询已关闭的数据库。
        await JobQueueServer.stop_job_queue()
        try:
            await JobQueuesTable.clear_task(time=0, include_active=True)
        except Exception:
            Logger.exception("Failed to clear job queues cleanly.")
        try:
            await asyncio.wait_for(close_web_render(), timeout=10)
        except TimeoutError:
            Logger.warning("Timed out while closing WebRender.")
        except Exception:
            Logger.exception("Failed to close WebRender cleanly.")
        try:
            await Tortoise.close_connections()
        except Exception:
            Logger.exception("Failed to close database connections cleanly.")


async def restart():
    """重启服务器。

    执行清理后强制退出并发出自定义状态码，上级进程会自动重启服务。
    """
    await cleanup_sessions()
    os._exit(233)
