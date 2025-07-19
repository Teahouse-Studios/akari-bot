import asyncio
import logging

from apscheduler.schedulers import SchedulerAlreadyRunningError

from core.constants import Info
from core.database import init_db
from core.logger import Logger
from core.queue.client import JobQueueClient
from core.scheduler import Scheduler, IntervalTrigger


async def check_queue() -> None:
    await JobQueueClient.check_job_queue()


async def client_init(target_prefix_list: list = None, sender_prefix_list: list = None, queue=True,
                      load_module_db=False) -> None:
    Logger.rename(Info.client_name)
    await init_db(load_module_db=load_module_db)
    if queue:
        asyncio.create_task(check_queue())
    await JobQueueClient.send_keepalive_signal_to_server(Info.client_name,
                                                         target_prefix_list=target_prefix_list,
                                                         sender_prefix_list=sender_prefix_list)

    @Scheduler.scheduled_job(IntervalTrigger(seconds=60))
    async def bg():
        await JobQueueClient.send_keepalive_signal_to_server(Info.client_name,
                                                             target_prefix_list=target_prefix_list,
                                                             sender_prefix_list=sender_prefix_list)

    try:
        Scheduler.start()
    except SchedulerAlreadyRunningError:
        pass
    logging.getLogger("apscheduler.executors.default").setLevel(logging.WARNING)
    Logger.info(f"Hello, {Info.client_name}!")
