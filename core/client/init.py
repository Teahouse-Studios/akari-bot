import asyncio
import logging

from apscheduler.schedulers import SchedulerAlreadyRunningError

from core.builtins.bot import Bot
from core.constants import Info
from core.database import init_db
from core.logger import Logger
from core.queue.client import JobQueueClient
from core.scheduler import Scheduler, IntervalTrigger
from core.i18n import connect_locale_snapshot


async def check_queue() -> None:
    await JobQueueClient.check_job_queue()


async def client_init(
    target_prefix_list: list | None = None,
    sender_prefix_list: list | None = None,
    queue=True,
    load_module_db=False,
    rename_logger: bool = True,
) -> None:
    if rename_logger:
        Logger.rename(Info.client_name)
    if not await init_db(load_module_db=load_module_db):
        raise RuntimeError(f"Failed to initialize database for {Info.client_name}.")
    if queue:
        asyncio.create_task(check_queue())
    await JobQueueClient.send_keepalive_signal_to_server(
        Info.client_name,
        target_prefix_list=target_prefix_list,
        sender_prefix_list=sender_prefix_list,
        ctx_slot_index=Bot.fetched_session_ctx_slot,
        features=Bot.ContextSlots[Bot.fetched_session_ctx_slot].features,
    )

    @Scheduler.scheduled_job(IntervalTrigger(seconds=60))
    async def bg():
        await JobQueueClient.send_keepalive_signal_to_server(
            Info.client_name,
            target_prefix_list=target_prefix_list,
            sender_prefix_list=sender_prefix_list,
            ctx_slot_index=Bot.fetched_session_ctx_slot,
            features=Bot.ContextSlots[Bot.fetched_session_ctx_slot].features,
        )

    try:
        Scheduler.start()
    except SchedulerAlreadyRunningError:
        pass
    logging.getLogger("apscheduler.executors.default").setLevel(logging.WARNING)
    connect_locale_snapshot("akari-bot")
    Logger.info(f"Hello, {Info.client_name}!")
