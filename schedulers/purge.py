import os
import shutil

from core.logger import Logger
from core.path import cache_path
from core.scheduler import Scheduler, CronTrigger


@Scheduler.scheduled_job(CronTrigger.from_crontab('0 0 * * *'))
async def auto_purge():
    Logger.info('Start purging cache...')
    if os.path.exists(cache_path):
        shutil.rmtree(cache_path)
    os.mkdir(cache_path)
