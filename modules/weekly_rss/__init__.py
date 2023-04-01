from core.builtins import Bot
from core.component import on_schedule
from core.logger import Logger
from core.scheduler import CronTrigger
from modules.weekly import get_weekly
from modules.weekly.teahouse import get_rss as get_teahouse_rss


@on_schedule('weekly_rss',
             trigger=CronTrigger.from_crontab('30 8 * * MON'),
             desc='开启后将订阅中文 Minecraft Wiki 的每周页面（每周一 8：30 更新）。',
             developers=['Dianliang233'], alias='weeklyrss')
async def weekly_rss(bot: Bot.FetchTarget):
    Logger.info('Checking MCWZH weekly...')

    weekly = await get_weekly(True if bot.name == 'QQ' else False)
    await bot.post_message('weekly_rss', weekly)
    Logger.info('Weekly checked.')


@on_schedule('teahouse_weekly_rss',
             trigger=CronTrigger.from_crontab('30 8 * * MON'), desc='开启后将订阅茶馆周报的每周页面（每周一 8：30 更新）。',
             developers=['OasisAkari'], alias=['teahouseweeklyrss', 'teahouserss'])
async def weekly_rss(bot: Bot.FetchTarget):
    Logger.info('Checking teahouse weekly...')

    weekly = await get_teahouse_rss()
    await bot.post_message('teahouse_weekly_rss', weekly)
    Logger.info('Teahouse Weekly checked.')
