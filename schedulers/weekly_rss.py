from core.builtins import Bot
from core.logger import Logger
from core.queue import JobQueue
from core.scheduler import CronTrigger, Scheduler
from modules.weekly import get_weekly
from modules.weekly.teahouse import get_rss as get_teahouse_rss


@Scheduler.scheduled_job(CronTrigger.from_crontab('0 9 * * MON'))
async def weekly_rss():
    Logger.info('Checking MCWZH weekly...')

    weekly_cn = await get_weekly(True if Bot.FetchTarget.name == 'QQ' else False)
    weekly_tw = await get_weekly(True if Bot.FetchTarget.name == 'QQ' else False, zh_tw=True)
    _weekly_cn = [i.to_dict() for i in weekly_cn]
    _weekly_tw = [i.to_dict() for i in weekly_tw]
    await JobQueue.trigger_hook_all('weekly_rss', weekly_cn=_weekly_cn, weekly_tw=_weekly_tw)


@Scheduler.scheduled_job(trigger=CronTrigger.from_crontab('30 9 * * MON'))
async def weekly_rss():
    Logger.info('Checking teahouse weekly...')

    weekly = await get_teahouse_rss()
    await JobQueue.trigger_hook_all('teahouse_weekly_rss', weekly=weekly)
