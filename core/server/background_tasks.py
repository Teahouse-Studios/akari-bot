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
from core.scheduler import Scheduler, IntervalTrigger
from core.utils.container import ExpiringTempDict
from core.web_render import init_web_render, web_render


@Scheduler.scheduled_job(IntervalTrigger(minutes=60))
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
    asyncio.create_task(fetch_ip_info())
    Logger.info("Starting WebRender...")
    await init_web_render()
    Info.web_render_status = await web_render.browser.check_status()
    if Info.web_render_status:
        Logger.success("WebRender started successfully.")
