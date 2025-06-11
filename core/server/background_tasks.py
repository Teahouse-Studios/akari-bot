import os
import shutil

from core.builtins.session.tasks import SessionTaskManager
from core.constants.path import cache_path
from core.scheduler import Scheduler, IntervalTrigger, CronTrigger
from core.utils.cooldown import clear_cd_list
from core.utils.game import clear_ps_list
from core.database.models import JobQueuesTable


@Scheduler.scheduled_job(IntervalTrigger(minutes=60))
async def bg():
    await SessionTaskManager.bg_check()
    await JobQueuesTable.clear_task()


@Scheduler.scheduled_job(CronTrigger.from_crontab("0 0 * * *"))
async def auto_purge():
    if os.path.exists(cache_path):
        shutil.rmtree(cache_path)
    os.makedirs(cache_path, exist_ok=True)


@Scheduler.scheduled_job(IntervalTrigger(seconds=1), max_instances=1)
async def clear_list():
    clear_cd_list()
    clear_ps_list()


def init_background_task():  # make IDE happy :)
    pass
