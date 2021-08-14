import asyncio
import traceback

from apscheduler.triggers.cron import CronTrigger

from core.loader.decorator import command
from core.logger import Logger
from core.scheduler import Scheduler
from database import BotDBUtil
from modules.weekly import get_weekly


@command('weekly_rss', autorun=True, help_doc=('{订阅中文 Minecraft Wiki 的每周页面（每周一 8：30 更新）。}'))
async def mcv_rss(bot):
    @Scheduler.scheduled_job(CronTrigger.from_crontab('30 8 * * MON'))
    async def check_weekly():
        Logger.info('Checking MCWZH weekly...')

        weekly = get_weekly()
        get_target_id = BotDBUtil.Module.get_enabled_this('weekly_rss')
        for x in get_target_id:
            fetch = bot.fetch_target(x)
            if fetch:
                try:
                    await fetch.sendMessage(weekly[0], weekly[1])
                    await asyncio.sleep(0.5)
                except Exception:
                    traceback.print_exc()
        Logger.info(weekly[0])
        Logger.info('Weekly checked.')
