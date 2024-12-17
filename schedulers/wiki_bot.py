from datetime import datetime, timedelta

from core.logger import Logger
from core.queue import JobQueue
from core.scheduler import DateTrigger, Scheduler, IntervalTrigger
from modules.wiki.utils.bot import BotAccount


@Scheduler.scheduled_job(DateTrigger(datetime.now() + timedelta(seconds=30)))
@Scheduler.scheduled_job(IntervalTrigger(minutes=30))
async def login_bots():
    Logger.info("Start login wiki bot account...")
    await BotAccount.login()
    await JobQueue.trigger_hook_all(
        "wiki_bot.login_wiki_bots", cookies=BotAccount.cookies
    )
    await JobQueue.trigger_hook_all("wikilog.keepalive")
    Logger.info("Successfully login wiki bot account.")
