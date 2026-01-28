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
async def _():
    await SessionTaskManager.bg_check()
    await JobQueuesTable.clear_task()


@Scheduler.scheduled_job(IntervalTrigger(seconds=1), max_instances=1)
async def _():
    await ExpiringTempDict.clear_all()


async def init_background_task():
    asyncio.create_task(fetch_ip_info())
    Logger.info("Starting WebRender...")
    await init_web_render()
    Info.web_render_status = await web_render.browser.check_status()
    if Info.web_render_status:
        Logger.success("WebRender started successfully.")
