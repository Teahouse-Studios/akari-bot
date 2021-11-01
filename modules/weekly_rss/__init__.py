from core.elements import CronTrigger, FetchTarget
from core.component import on_schedule
from core.logger import Logger
from modules.weekly import get_weekly


@on_schedule('weekly_rss',
             trigger=CronTrigger.from_crontab('30 8 * * MON'), desc='订阅中文 Minecraft Wiki 的每周页面（每周一 8：30 更新）。',
             developers=['Dianliang233'])
async def weekly_rss(bot: FetchTarget):
    Logger.info('Checking MCWZH weekly...')

    weekly = await get_weekly()
    await bot.post_message('weekly_rss', weekly)
    Logger.info('Weekly checked.')
