import asyncio
import logging

from akari_bot_i18n.i18n import load_locale_file
from apscheduler.schedulers import SchedulerAlreadyRunningError

from core.constants import Info, lang_list, all_locales_path
from core.database import init_db
from core.logger import Logger
from core.queue.client import JobQueueClient
from core.scheduler import Scheduler, IntervalTrigger


async def check_queue() -> None:
    await JobQueueClient.check_job_queue()


async def client_init(
    target_prefix_list: list = None, sender_prefix_list: list = None, queue=True, load_module_db=False
) -> None:
    Logger.rename(Info.client_name)
    load_locale_file(list(lang_list.keys()), all_locales_path)
    await init_db(load_module_db=load_module_db)
    if queue:
        asyncio.create_task(check_queue())
    await JobQueueClient.send_keepalive_signal_to_server(
        Info.client_name,
        target_prefix_list=target_prefix_list,
        sender_prefix_list=sender_prefix_list,
        require_check_dirty_words=Info.dirty_word_check,
        use_url_manager=Info.use_url_manager,
        use_url_md_format=Info.use_url_md_format,
    )

    @Scheduler.scheduled_job(IntervalTrigger(seconds=60))
    async def bg():
        await JobQueueClient.send_keepalive_signal_to_server(
            Info.client_name,
            target_prefix_list=target_prefix_list,
            sender_prefix_list=sender_prefix_list,
            require_check_dirty_words=Info.dirty_word_check,
            use_url_manager=Info.use_url_manager,
            use_url_md_format=Info.use_url_md_format,
        )

    try:
        Scheduler.start()
    except SchedulerAlreadyRunningError:
        pass
    logging.getLogger("apscheduler.executors.default").setLevel(logging.WARNING)
    Logger.info(f"Hello, {Info.client_name}!")
