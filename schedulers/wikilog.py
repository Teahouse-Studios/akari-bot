from datetime import datetime, timedelta

from core.logger import Logger
from core.queue import JobQueue
from core.scheduler import DateTrigger, Scheduler, CronTrigger, IntervalTrigger
from modules.wikilog.dbutils import WikiLogUtil
from core.utils.http import get_url


fetch_cache = {}


@Scheduler.scheduled_job(IntervalTrigger(seconds=60))
async def _():
    fetches = WikiLogUtil.return_all_data()
    for id_ in fetches:
        Logger.debug(f'Checking fetch {id_}...')
