from datetime import datetime, timedelta

from core.logger import Logger
from core.queue import JobQueue
from core.scheduler import DateTrigger, Scheduler
from modules.wiki.utils.bot import BotAccount


@Scheduler.scheduled_job(DateTrigger(datetime.now() + timedelta(seconds=30)))
async def login_bots():
    Logger.info('Start login wiki bot account...')
    await BotAccount.login()
    await JobQueue.trigger_hook_all('wiki_audit.login_wiki_bots', cookies=BotAccount.cookies)
    Logger.info('Successfully login wiki bot account.')
