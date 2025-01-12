from core.builtins import MessageTaskManager
from core.queue import check_job_queue, JobQueue
from core.scheduler import Scheduler, IntervalTrigger


@Scheduler.scheduled_job(IntervalTrigger(minutes=60))
async def bg():
    await MessageTaskManager.bg_check()


@Scheduler.scheduled_job(IntervalTrigger(seconds=1), max_instances=1)
async def job():
    await check_job_queue()


async def init_background_task():
    await JobQueue.add_job(JobQueue.name, "verify_timezone", {}, wait=False)
