'''基于apscheduler的计划任务。'''
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.combining import AndTrigger, OrTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

Scheduler = AsyncIOScheduler()

__all__ = ["Scheduler", "AndTrigger", "OrTrigger", "CronTrigger", "DateTrigger", "IntervalTrigger"]
