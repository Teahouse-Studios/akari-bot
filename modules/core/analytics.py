from datetime import datetime, timedelta, UTC

import matplotlib.pyplot as plt
from dateutil.relativedelta import relativedelta
from tortoise.exceptions import DoesNotExist

from core.builtins.bot import Bot
from core.builtins.message.internal import Image, I18NContext, FormattedTime
from core.component import module
from core.config.base import CoreConfig
from core.database.models import AnalyticsData
from core.logger import Logger
from core.utils.cache import random_cache_path

enable_analytics = CoreConfig.enable_analytics


async def get_first_record():
    try:
        first_record = await AnalyticsData.get(id=1)
        ts = first_record.timestamp.replace(tzinfo=UTC).timestamp()
        return str(FormattedTime(ts, iso=True))
    except DoesNotExist:
        return None
    except Exception:
        Logger.exception()


def local_midnight() -> datetime:
    """
    取本地时区的今日零点，且带上时区信息。

    统计窗口按运行机器的本地日历切分。Tortoise 启用了时区支持，不带时区的时间会被一律
    当作 UTC 处理：既触发 RuntimeWarning，也会让整个窗口偏移一个时区差，落在偏移量内的
    记录会被算进相邻的一天。因此这里必须显式附上本地时区，微秒也要一并清零。

    :return: 带本地时区的今日零点。
    """
    return datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)


def annotate_points(data_x: list[str], data_y: list[int]) -> None:
    """
    在折线的各数据点上方标注数值，并按需抬高 y 轴上限。

    标注按相对数据点的像素偏移放置，这类标注不参与坐标轴的自动缩放，默认 5% 的上边距
    放不下最高点的标注，标注会顶出坐标区。故在绘制后量出标注实际向上占用的像素高度，
    再据此反推 y 轴上限应抬到何处，这样与数据量级、图幅大小均无关。

    :param data_x: 横轴刻度。
    :param data_y: 纵轴数值。
    """
    ax = plt.gca()
    annotations = [
        ax.annotate(y, (x, y), textcoords="offset points", xytext=(0, 10), ha="center") for x, y in zip(data_x, data_y)
    ]
    figure = ax.get_figure()
    figure.canvas.draw()

    axes_height = ax.get_window_extent().height
    # 标注相对其数据点向上占去的像素高度，另留 4 磅间距避免标注正好贴住顶边框
    headroom = (
        max(
            annotation.get_window_extent().y1 - ax.transData.transform((0, y))[1]
            for annotation, y in zip(annotations, data_y)
        )
        + 4 * figure.dpi / 72
    )
    if headroom >= axes_height:
        return

    bottom, top = ax.get_ylim()
    # 令最高点落在「坐标区顶端往下 headroom 像素」处；取较大者以保证只抬高、不压缩
    needed_top = bottom + (max(data_y) - bottom) * axes_height / (axes_height - headroom)
    ax.set_ylim(bottom, max(top, needed_top))


ana = module("analytics", alias="ana", required_superuser=True, base=True, doc=True)


@ana.command()
async def _(msg: Bot.MessageSession):
    if enable_analytics:
        first_record = await get_first_record()
        if not first_record:
            await msg.finish(I18NContext("core.message.analytics.none"))
        get_counts = await AnalyticsData.all().count()

        old = local_midnight()
        new = old + timedelta(days=1)
        get_counts_today = await AnalyticsData.get_count_by_times(new, old)

        await msg.finish(
            I18NContext(
                "core.message.analytics.counts",
                first_record=first_record,
                counts=get_counts,
                counts_today=get_counts_today,
            )
        )
    else:
        await msg.finish(I18NContext("core.message.analytics.disabled"))


@ana.command("days [<module>]")
async def _(msg: Bot.MessageSession):
    if enable_analytics:
        first_record = await get_first_record()
        if not first_record:
            await msg.finish(I18NContext("core.message.analytics.none"))
        module_ = msg.parsed_msg.get("<module>")
        if not module_:
            result = I18NContext("core.message.analytics.days.total", first_record=first_record)
        else:
            result = I18NContext(
                "core.message.analytics.days",
                module=module_,
                first_record=first_record,
            )
        data_ = {}
        # 零点在循环外取一次：逐次取会在跨零点时把前后两天的边界混在一起
        midnight = local_midnight()
        for d in range(30):
            old = midnight - timedelta(days=29 - d)
            new = old + timedelta(days=1)
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
        annotate_points(data_x, data_y)
        path = f"{random_cache_path()}.png"
        plt.savefig(path)
        plt.close()
        await msg.finish([result, Image(path)])
    else:
        await msg.finish(I18NContext("core.message.analytics.disabled"))


@ana.command("year [<module>]")
async def _(msg: Bot.MessageSession):
    if enable_analytics:
        first_record = await get_first_record()

        if not first_record:
            await msg.finish(I18NContext("core.message.analytics.none"))
        module_ = msg.parsed_msg.get("<module>")
        if not module_:
            result = I18NContext("core.message.analytics.year.total", first_record=first_record)
        else:
            result = I18NContext(
                "core.message.analytics.year",
                module=module_,
                first_record=first_record,
            )
        data_ = {}
        # 本月一日在循环外取一次：逐次取会在跨零点时把前后两个月的边界混在一起
        first_day = local_midnight().replace(day=1)
        for m in range(12):
            old = first_day - relativedelta(months=11 - m)
            new = old + relativedelta(months=1)
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
        annotate_points(data_x, data_y)
        path = f"{random_cache_path()}.png"
        plt.savefig(path)
        plt.close()
        await msg.finish([result, Image(path)])
    else:
        await msg.finish(I18NContext("core.message.analytics.disabled"))


@ana.command("modules [<rank>]")
async def _(msg: Bot.MessageSession, rank: int | None = None):
    rank = rank if rank and rank > 0 else 30
    if enable_analytics:
        try:
            module_counts = await AnalyticsData.get_modules_count()
            top_modules = sorted(module_counts.items(), key=lambda x: x[1], reverse=True)[:rank]

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
                Logger.exception()
    else:
        await msg.finish(I18NContext("core.message.analytics.disabled"))
