from datetime import datetime, timedelta

from core.builtins import Bot
from core.logger import Logger
from core.queue import JobQueue
from core.scheduler import DateTrigger, Scheduler
from modules.wiki import BotAccount


@Scheduler.scheduled_job(DateTrigger(datetime.now() + timedelta(seconds=10)))
async def login_bots():
    Logger.info('Start login wiki bot account...')
    await BotAccount.login()
    await JobQueue.trigger_hook_all('login_wiki_bots', cookies=BotAccount.cookies)
    Logger.info('Login wiki bot account done')
