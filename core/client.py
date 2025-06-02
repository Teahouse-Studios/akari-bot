import asyncio

from apscheduler.schedulers import SchedulerAlreadyRunningError

from core.constants import Info
from core.database import init_db
from core.logger import Logger
from core.queue.client import JobQueueClient
from core.scheduler import Scheduler, IntervalTrigger


async def check_queue() -> None:
    while True:
        await JobQueueClient.check_job_queue()
        await asyncio.sleep(0.1)


async def client_init(target_prefix_list: list = None, sender_prefix_list: list = None) -> None:
    await init_db()
    asyncio.create_task(check_queue())
    await JobQueueClient.send_keepalive_signal_to_server(Info.client_name,
                                                         target_prefix_list=target_prefix_list,
                                                         sender_prefix_list=sender_prefix_list)

    @Scheduler.scheduled_job(IntervalTrigger(minutes=60))
    async def bg():
        await JobQueueClient.send_keepalive_signal_to_server(Info.client_name,
                                                             target_prefix_list=target_prefix_list,
                                                             sender_prefix_list=sender_prefix_list)
    try:
        Scheduler.start()
    except SchedulerAlreadyRunningError:
        Logger.warning("Scheduler is already running, skipping start.")
    Logger.info(f"Hello, {Info.client_name}!")
