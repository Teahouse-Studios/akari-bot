import asyncio
import random
import traceback

from apscheduler.triggers.cron import CronTrigger

from core.loader.decorator import schedule
from core.elements import CronTrigger, FetchTarget
from core.logger import Logger
from core.scheduler import Scheduler
from database import BotDBUtil
from modules.weekly import get_weekly


@schedule('weekly_rss', trigger=CronTrigger.from_crontab('30 8 * * MON'), desc='订阅中文 Minecraft Wiki 的每周页面（每周一 8：30 更新）。')
async def weekly_rss(bot: FetchTarget):
    Logger.info('Checking MCWZH weekly...')

    weekly = await get_weekly()
    await bot.post_message('weekly_rss', weekly)
    Logger.info(weekly[0])
    Logger.info('Weekly checked.')
