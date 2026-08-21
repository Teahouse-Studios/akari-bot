"""
服务器后台任务模块。

定义服务器启动后运行的后台任务，包括：
- 定期的会话检查和清理
- 过期临时数据清理
- IP 信息获取
- WebRender 初始化
"""

import asyncio

from core.builtins.session.tasks import SessionTaskManager
from core.constants import Info
from core.database.models import JobQueuesTable
from core.ip import fetch_ip_info
from core.logger import Logger
from core.utils.container import ExpiringTempDict
from core.web_render import check_web_render_status, init_web_render


_background_task: asyncio.Task[None] | None = None


async def hourly_background_task():
    """每小时执行一次的后台检查任务。

    功能：
    - 执行会话的后台检查
    - 清理已完成的任务队列
    - 清理过期的临时数据
    """
    await SessionTaskManager.bg_check()
    await JobQueuesTable.clear_task()
    await ExpiringTempDict.clear_all()


async def init_background_task():
    """初始化后台任务。

    启动以下服务：
    1. IP信息获取
    2. WebRender 初始化
    3. 检查并记录 WebRender 状态
    """

    async def _init_web_render():
        Logger.info("Starting WebRender...")
        try:
            await init_web_render()
            Info.web_render_status = await check_web_render_status()
            if Info.web_render_status:
                Logger.success("WebRender started successfully.")
        except asyncio.CancelledError:
            raise
        except Exception:
            Info.web_render_status = False
            Logger.exception("Failed to initialize WebRender.")

    # 两项初始化并行执行，并保持结构化并发语义：任一任务意外失败时，TaskGroup
    # 会取消并等待另一个任务，避免父任务已经结束、浏览器初始化却仍在后台继续。
    async with asyncio.TaskGroup() as group:
        group.create_task(fetch_ip_info(), name="server-ip-info-init")
        group.create_task(_init_web_render(), name="server-web-render-init")


def _background_task_done(task: asyncio.Task[None]) -> None:
    """取回后台初始化任务的异常，避免出现 ``Task exception was never retrieved``。"""
    try:
        task.result()
    except asyncio.CancelledError:
        pass
    except Exception:
        Logger.exception("Server background initialization failed.")


def start_background_task() -> asyncio.Task[None]:
    """启动并持有 Server 后台初始化任务；重复调用时复用仍在运行的任务。"""
    global _background_task
    if _background_task is None or _background_task.done():
        _background_task = asyncio.create_task(init_background_task(), name="server-background-init")
        _background_task.add_done_callback(_background_task_done)
    return _background_task


async def stop_background_task() -> None:
    """取消并等待后台初始化，保证 WebRender 关闭不会与浏览器启动并发。"""
    global _background_task
    task = _background_task
    _background_task = None
    if task is None:
        return
    if not task.done():
        task.cancel()
    await asyncio.gather(task, return_exceptions=True)


__all__ = [
    "hourly_background_task",
    "init_background_task",
    "start_background_task",
    "stop_background_task",
]
