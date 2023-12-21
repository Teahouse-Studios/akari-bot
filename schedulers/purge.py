import os
import shutil

from config import Config
from core.logger import Logger
from core.scheduler import Scheduler, CronTrigger


@Scheduler.scheduled_job(CronTrigger.from_crontab('0 0 * * *'))
async def _():
    cache_path = os.path.abspath(Config('cache_path'))
    Logger.info('Start purging cache...')
    if os.path.exists(cache_path):
        shutil.rmtree(cache_path)
    os.mkdir(cache_path)
