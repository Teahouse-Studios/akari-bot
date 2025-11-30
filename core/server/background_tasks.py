import asyncio

from akari_bot_webrender.functions.options import StatusOptions

from core.builtins.session.tasks import SessionTaskManager
from core.constants import Info
from core.cooldown import clear_expired_cooldown
from core.database.models import JobQueuesTable
from core.game import clear_expired_playstate
from core.ip import fetch_ip_info
from core.logger import Logger
from core.scheduler import Scheduler, IntervalTrigger
from core.web_render import init_web_render, web_render


@Scheduler.scheduled_job(IntervalTrigger(minutes=60))
async def bg():
    await SessionTaskManager.bg_check()
    await JobQueuesTable.clear_task()


@Scheduler.scheduled_job(IntervalTrigger(seconds=1), max_instances=1)
async def clear_timetempdict():
    clear_expired_cooldown()
    clear_expired_playstate()


async def init_background_task():
    asyncio.create_task(fetch_ip_info())
    Logger.info("Starting WebRender...")
    await init_web_render()
    Info.web_render_status = await web_render.browser.check_status()
    if Info.web_render_status:
        Logger.success("WebRender started successfully.")
