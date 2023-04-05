from core.builtins import Bot
from core.component import module
from core.logger import Logger
from core.scheduler import CronTrigger
from modules.weekly import get_weekly
from modules.weekly.teahouse import get_rss as get_teahouse_rss

weekly_rss = module('weekly_rss',
                    desc='{weekly_rss.help.desc}',
                    developers=['Dianliang233'], alias='weeklyrss')


@weekly_rss.handle(CronTrigger.from_crontab('30 8 * * MON'))
async def weekly_rss():
    Logger.info('Checking MCWZH weekly...')

    weekly = await get_weekly(True if Bot.FetchTarget.name == 'QQ' else False)
    await Bot.FetchTarget.post_message('weekly_rss', weekly)
    Logger.info('Weekly checked.')


teahouse_weekly_rss = module('teahouse_weekly_rss',

                             desc='{teahouse_weekly_rss.help.desc}',
                             developers=['OasisAkari'], alias=['teahouseweeklyrss', 'teahouserss'])


@teahouse_weekly_rss.handle(trigger=CronTrigger.from_crontab('30 8 * * MON'))
async def weekly_rss():
    Logger.info('Checking teahouse weekly...')

    weekly = await get_teahouse_rss()
    await Bot.FetchTarget.post_message('teahouse_weekly_rss', weekly)
    Logger.info('Teahouse Weekly checked.')
