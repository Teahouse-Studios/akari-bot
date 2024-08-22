from datetime import datetime, timedelta

from core.logger import Logger
from core.queue import JobQueue
from core.scheduler import DateTrigger, Scheduler, CronTrigger
from modules.wiki.utils.bot import BotAccount


@Scheduler.scheduled_job(DateTrigger(datetime.now() + timedelta(seconds=30)))
@Scheduler.scheduled_job(CronTrigger(hour='0', minute='0', second='0'))
async def login_bots():
    Logger.info('Start login wiki bot account...')
    await BotAccount.login()
    await JobQueue.trigger_hook_all('wiki_bot.login_wiki_bots', cookies=BotAccount.cookies)
    Logger.info('Successfully login wiki bot account.')
