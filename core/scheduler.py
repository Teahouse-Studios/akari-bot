'''基于apscheduler的计划任务。'''
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.combining import AndTrigger, OrTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from core.builtins import MessageTaskManager

Scheduler = AsyncIOScheduler()


@Scheduler.scheduled_job(IntervalTrigger(minutes=60))
async def bg():
    await MessageTaskManager.bg_check()


__all__ = ["Scheduler", "AndTrigger", "OrTrigger", "CronTrigger", "DateTrigger", "IntervalTrigger"]
