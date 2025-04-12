import traceback
from datetime import datetime, timedelta, UTC

import matplotlib.pyplot as plt
from dateutil.relativedelta import relativedelta

from core.builtins import Bot, Plain, Image, I18NContext
from core.component import module
from core.config import Config
from core.database.models import AnalyticsData
from core.logger import Logger
from core.utils.cache import random_cache_path


async def get_first_record(msg: Bot.MessageSession):
    first_record = await AnalyticsData.get(id=1)
    ts = first_record.timestamp.replace(tzinfo=UTC).timestamp()
    return msg.ts2strftime(ts, iso=True, timezone=False)


ana = module("analytics", alias="ana", required_superuser=True, base=True, doc=True)


@ana.command()
async def _(msg: Bot.MessageSession):
    if Config("enable_analytics", False):
        try:
            first_record = await get_first_record(msg)
            get_counts = await AnalyticsData.all().count()

            new = datetime.now().replace(hour=0, minute=0, second=0) + timedelta(days=1)
            old = datetime.now().replace(hour=0, minute=0, second=0)
            get_counts_today = await AnalyticsData.get_count_by_times(new, old)

            await msg.finish(I18NContext(
                "core.message.analytics.counts",
                first_record=first_record,
                counts=get_counts,
                counts_today=get_counts_today))
        except AttributeError as e:
            if str(e).find("NoneType") != -1:
                await msg.finish(I18NContext("core.message.analytics.none"))
            else:
                Logger.error(traceback.format_exc())
    else:
        await msg.finish(I18NContext("core.message.analytics.disabled"))


@ana.command("days [<module>]")
async def _(msg: Bot.MessageSession):
    if Config("enable_analytics", False):
        try:
            first_record = await get_first_record(msg)
            module_ = msg.parsed_msg.get("<module>")
            if not module_:
                result = I18NContext(
                    "core.message.analytics.days.total", first_record=first_record
                )
            else:
                result = I18NContext(
                    "core.message.analytics.days",
                    module=module_,
                    first_record=first_record,
                )
            data_ = {}
            for d in range(30):
                new = (
                    datetime.now().replace(hour=0, minute=0, second=0)
                    + timedelta(days=1)
                    - timedelta(days=30 - d - 1)
                )
                old = (
                    datetime.now().replace(hour=0, minute=0, second=0)
                    + timedelta(days=1)
                    - timedelta(days=30 - d)
                )
                get_ = await AnalyticsData.get_count_by_times(new, old, module_)
                data_[old.day] = get_
            data_x = []
            data_y = []
            for x in data_:
                data_x.append(str(x))
                data_y.append(data_[x])
            plt.plot(data_x, data_y, "-o")
            plt.plot(data_x[-1], data_y[-1], "-ro")
            plt.xlabel("Days")
            plt.ylabel("Counts")
            plt.tick_params(axis="x", labelrotation=45, which="major", labelsize=10)

            plt.gca().yaxis.get_major_locator().set_params(integer=True)
            for xitem, yitem in zip(data_x, data_y):
                plt.annotate(
                    yitem,
                    (xitem, yitem),
                    textcoords="offset points",
                    xytext=(0, 10),
                    ha="center",
                )
            path = f"{random_cache_path()}.png"
            plt.savefig(path)
            plt.close()
            await msg.finish([result, Image(path)])
        except AttributeError as e:
            if str(e).find("NoneType") != -1:
                await msg.finish(I18NContext("core.message.analytics.none"))
            else:
                Logger.error(traceback.format_exc())
    else:
        await msg.finish(I18NContext("core.message.analytics.disabled"))


@ana.command("year [<module>]")
async def _(msg: Bot.MessageSession):
    if Config("enable_analytics", False):
        try:
            first_record = await get_first_record(msg)
            module_ = msg.parsed_msg.get("<module>")
            if not module_:
                result = I18NContext(
                    "core.message.analytics.year.total", first_record=first_record
                )
            else:
                result = I18NContext(
                    "core.message.analytics.year",
                    module=module_,
                    first_record=first_record,
                )
            data_ = {}
            for m in range(12):
                new = (
                    datetime.now().replace(day=1, hour=0, minute=0, second=0)
                    + relativedelta(months=1)
                    - relativedelta(months=12 - m - 1)
                )
                old = (
                    datetime.now().replace(day=1, hour=0, minute=0, second=0)
                    + relativedelta(months=1)
                    - relativedelta(months=12 - m)
                )
                get_ = await AnalyticsData.get_count_by_times(new, old, module_)
                data_[old.month] = get_
            data_x = []
            data_y = []
            for x in data_:
                data_x.append(str(x))
                data_y.append(data_[x])
            plt.plot(data_x, data_y, "-o")
            plt.plot(data_x[-1], data_y[-1], "-ro")
            plt.xlabel("Months")
            plt.ylabel("Counts")
            plt.tick_params(axis="x", labelrotation=45, which="major", labelsize=10)

            plt.gca().yaxis.get_major_locator().set_params(integer=True)
            for xitem, yitem in zip(data_x, data_y):
                plt.annotate(
                    yitem,
                    (xitem, yitem),
                    textcoords="offset points",
                    xytext=(0, 10),
                    ha="center",
                )
            path = f"{random_cache_path()}.png"
            plt.savefig(path)
            plt.close()
            await msg.finish([result, Image(path)])
        except AttributeError as e:
            if str(e).find("NoneType") != -1:
                await msg.finish(I18NContext("core.message.analytics.none"))
            else:
                Logger.error(traceback.format_exc())
    else:
        await msg.finish(I18NContext("core.message.analytics.disabled"))


@ana.command("modules [<rank>]")
async def _(msg: Bot.MessageSession, rank: int = None):
    rank = rank if rank and rank > 0 else 30
    if Config("enable_analytics", False):
        try:
            module_counts = await AnalyticsData.get_modules_count()
            top_modules = sorted(
                module_counts.items(), key=lambda x: x[1], reverse=True
            )[:rank]

            module_names = [item[0] for item in top_modules]
            module_counts = [item[1] for item in top_modules]
            plt.figure(figsize=(10, max(6, len(module_names) * 0.5)))
            plt.barh(module_names, module_counts, color="skyblue")
            plt.xlabel("Counts")
            plt.ylabel("Modules")
            plt.gca().invert_yaxis()

            for i, v in enumerate(module_counts):
                plt.text(v, i, str(v), color="black", va="center")

            path = f"{random_cache_path()}.png"
            plt.savefig(path, bbox_inches="tight")
            plt.close()

            await msg.finish([Image(path)])
        except AttributeError as e:
            if str(e).find("NoneType") != -1:
                await msg.finish(I18NContext("core.message.analytics.none"))
            else:
                Logger.error(traceback.format_exc())
    else:
        await msg.finish(I18NContext("core.message.analytics.disabled"))
