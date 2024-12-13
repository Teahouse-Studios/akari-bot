from datetime import datetime, timedelta

from core.constants import Info
from core.logger import Logger
from core.queue import JobQueue
from core.scheduler import DateTrigger, Scheduler
from core.utils.web_render import check_web_render



@Scheduler.scheduled_job(DateTrigger(datetime.now() + timedelta(seconds=10)))
async def check_webrender():
    Logger.info('Checking webrender...')
    await check_web_render()

    await JobQueue.web_render_status(web_render_status=Info.web_render_status,
                                    web_render_local_status=Info.web_render_local_status)
    Logger.info('Successfully checked webrender.')
