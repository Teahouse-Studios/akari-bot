from core.builtins import MessageTaskManager
from core.queue import check_job_queue
from core.scheduler import Scheduler, IntervalTrigger
from core.utils.cooldown import clear_cd_list
from core.utils.game import clear_ps_list


@Scheduler.scheduled_job(IntervalTrigger(minutes=60))
async def bg():
    await MessageTaskManager.bg_check()


@Scheduler.scheduled_job(IntervalTrigger(seconds=1), max_instances=1)
async def job():
    await check_job_queue()


@Scheduler.scheduled_job(IntervalTrigger(seconds=1), max_instances=1)
async def clear():
    clear_cd_list()
    clear_ps_list()


def init_background_task():  # make IDE happy :)
    pass
