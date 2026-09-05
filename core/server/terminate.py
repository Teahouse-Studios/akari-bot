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

from tortoise import Tortoise

# from core.builtins.session.tasks import SessionTaskManager
from core.database.models import JobQueuesTable
from core.logger import Logger
from core.queue.server import JobQueueServer
from core.scheduler import SchedulerLifecycle
from core.utils.web_render import close_web_render
from .background_tasks import stop_background_task
from .lifecycle import BackgroundTaskLifecycle


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
    # 先同步关闭 Scheduler 的新任务入口；真正取消／等待运行中 Job 放在其它 Queue
    # handler 取消之后执行，避免正在 reload_db 的 handler 持有 Scheduler 维护锁时
    # 与 restart action 互相等待。
    SchedulerLifecycle.begin_shutdown()
    # 先关闭新 action 入口并与已经开始领取的一轮轮询建立屏障。轮询器仍继续回收
    # 在途 RPC 的远端结果，供下面取消任务时释放平台 context。
    await JobQueueServer.begin_shutdown()
    # Queue handler 可能持有 Scheduler 维护锁，也可能在退出路径创建 detached task。
    # 先取消并等待它们，再关闭 Scheduler，最后统一清理所有已注册后台任务。
    await JobQueueServer.cancel_process_tasks()
    try:
        await SchedulerLifecycle.shutdown()
    except Exception:
        Logger.exception("Failed to stop scheduler cleanly.")
    try:
        await stop_background_task()
    except Exception:
        Logger.exception("Failed to stop background initialization cleanly.")
    # 注册项可能持有 MessageSession context，取消时会经 Queue 请求平台进程 release，
    # 因此必须在停止 poller 之前执行。只有实际导入过的组件会注册，不会在关闭阶段
    # 为清理而额外导入未加载模块。
    await BackgroundTaskLifecycle.run_cleanup()
    # restart() 可能由 Queue action 自身触发，此时主循环的轮询器仍在运行。关闭窗口
    # 必须先阻止它继续领取任务，再取消其它 handler，并在独占轮询锁时清库、关资源；
    # 否则清空队列或关闭连接期间仍可能启动一个新的平台副作用。
    async with JobQueueServer.shutdown_window():
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
