import os
import shutil

from config import Config
from core.logger import Logger
from core.scheduler import Scheduler, CronTrigger


@Scheduler.scheduled_job(CronTrigger.from_crontab('0 0 * * *'))
async def auto_purge():
    Logger.info('Start purging cache...')
    cache_path = os.path.abspath(Config('cache_path'))
    if os.path.exists(cache_path):
        shutil.rmtree(cache_path)
    os.mkdir(cache_path)
