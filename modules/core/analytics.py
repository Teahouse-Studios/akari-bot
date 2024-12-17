import traceback
from datetime import datetime, timedelta, timezone
from typing import Tuple

import matplotlib.pyplot as plt
from dateutil.relativedelta import relativedelta

from core.builtins import Bot, Plain, Image
from core.component import module
from core.config import Config
from core.database import BotDBUtil
from core.database.tables import is_mysql
from core.logger import Logger
from core.utils.cache import random_cache_path


def get_first_record(msg: Bot.MessageSession):
    if is_mysql:
        first_record = BotDBUtil.Analytics.get_first().timestamp.timestamp()
    else:
        first_record = (
            BotDBUtil.Analytics.get_first()
            .timestamp.replace(tzinfo=timezone.utc)
            .timestamp()
        )
    return msg.ts2strftime(first_record, iso=True, timezone=False)


ana = module("analytics", alias="ana", required_superuser=True, base=True, doc=True)


@ana.command()
async def _(msg: Bot.MessageSession):
    if Config("enable_analytics", False):
        try:
            first_record = get_first_record(msg)
            get_counts = BotDBUtil.Analytics.get_count()

            new = datetime.now().replace(hour=0, minute=0, second=0) + timedelta(days=1)
            old = datetime.now().replace(hour=0, minute=0, second=0)
            get_counts_today = BotDBUtil.Analytics.get_count_by_times(new, old)

            await msg.finish(
                msg.locale.t(
                    "core.message.analytics.counts",
                    first_record=first_record,
                    counts=get_counts,
                    counts_today=get_counts_today,
                )
            )
        except AttributeError as e:
            if str(e).find("NoneType") != -1:
                await msg.finish(msg.locale.t("core.message.analytics.none"))
            else:
                Logger.error(traceback.format_exc())
    else:
        await msg.finish(msg.locale.t("core.message.analytics.disabled"))


@ana.command("days [<module>]")
async def _(msg: Bot.MessageSession):
    if Config("enable_analytics", False):
        try:
            first_record = get_first_record(msg)
            module_ = msg.parsed_msg.get("<module>")
            if not module_:
                result = msg.locale.t(
                    "core.message.analytics.days.total", first_record=first_record
                )
            else:
                result = msg.locale.t(
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
                get_ = BotDBUtil.Analytics.get_count_by_times(new, old, module_)
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
            await msg.finish([Plain(result), Image(path)])
        except AttributeError as e:
            if str(e).find("NoneType") != -1:
                await msg.finish(msg.locale.t("core.message.analytics.none"))
            else:
                Logger.error(traceback.format_exc())
    else:
        await msg.finish(msg.locale.t("core.message.analytics.disabled"))


@ana.command("year [<module>]")
async def _(msg: Bot.MessageSession):
    if Config("enable_analytics", False):
        try:
            first_record = get_first_record(msg)
            module_ = msg.parsed_msg.get("<module>")
            if not module_:
                result = msg.locale.t(
                    "core.message.analytics.year.total", first_record=first_record
                )
            else:
                result = msg.locale.t(
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
                get_ = BotDBUtil.Analytics.get_count_by_times(new, old, module_)
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
            await msg.finish([Plain(result), Image(path)])
        except AttributeError as e:
            if str(e).find("NoneType") != -1:
                await msg.finish(msg.locale.t("core.message.analytics.none"))
            else:
                Logger.error(traceback.format_exc())
    else:
        await msg.finish(msg.locale.t("core.message.analytics.disabled"))


@ana.command("modules [<rank>]")
async def _(msg: Bot.MessageSession, rank: int = None):
    rank = rank if rank and rank > 0 else 30
    if Config("enable_analytics", False):
        try:
            module_counts = BotDBUtil.Analytics.get_modules_count()
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
                await msg.finish(msg.locale.t("core.message.analytics.none"))
            else:
                Logger.error(traceback.format_exc())
    else:
        await msg.finish(msg.locale.t("core.message.analytics.disabled"))


@ana.command("export")
async def _(msg: Bot.MessageSession):
    # if config('enable_analytics', False):
    #     await msg.send_message(msg.locale.t("core.message.analytics.export.waiting"))
    #     expires = config('analytics_expires', 600)
    #     url = export_analytics(expires=expires)
    #     url_b64 = base64.b64encode(url.encode()).decode()
    #     await msg.finish(msg.locale.t("core.message.analytics.export",
    #                                   url=config('analytics_url') + '?data_input=' + url_b64, expires=expires))
    # else:
    #     await msg.finish(msg.locale.t("core.message.analytics.disabled"))
    ...


def export_analytics(
    from_to: Tuple[datetime, datetime] = None,
    commands: bool = False,
    expires: int = 600,
):
    # oss_ak = config('oss_ak', secret=True)
    # oss_sk = config('oss_sk', secret=True)
    # oss_endpoint = config('oss_endpoint')
    # oss_bucket = config('oss_bucket')
    # if not oss_ak or not oss_sk or not oss_endpoint or not oss_bucket:
    #     raise ValueError('Aliyun OSS credentials not found.')
    # analytics_data = {}
    # modules_list = []
    # if from_to:
    #     query = session.query(AnalyticsData).filter(
    #         AnalyticsData.timestamp >= from_to[0],
    #         AnalyticsData.timestamp <= from_to[1])
    # else:
    #     query = session.query(AnalyticsData)
    # query_count = query.count()
    # queried = 0
    # while query_count:
    #     if query_count > 1000:
    #         queried_next = queried + 1000
    #         query_count -= 1000
    #     else:
    #         queried_next = queried + query_count
    #         query_count = 0
    #     query_slice = query.slice(queried, queried_next).all()
    #     for data in query_slice:
    #         time_key = data.timestamp.strftime("%Y-%m-%d")
    #         if time_key not in analytics_data:
    #             analytics_data[time_key] = {}
    #         if data.senderId not in analytics_data[time_key]:
    #             analytics_data[time_key][data.senderId] = {}
    #         if data.targetId not in analytics_data[time_key][data.senderId]:
    #             analytics_data[time_key][data.senderId][data.targetId] = {}
    #         if data.moduleName not in analytics_data[time_key][data.senderId][data.targetId]:
    #             analytics_data[time_key][data.senderId][data.targetId][data.moduleName] = {}
    #         if 'commands' not in analytics_data[time_key][data.senderId][data.targetId][data.moduleName] and commands:
    #             analytics_data[time_key][data.senderId][data.targetId][data.moduleName]['commands'] = []
    #         if 'count' not in analytics_data[time_key][data.senderId][data.targetId][data.moduleName]:
    #             analytics_data[time_key][data.senderId][data.targetId][data.moduleName]['count'] = 0
    #         if 'type' not in analytics_data[time_key][data.senderId][data.targetId][data.moduleName]:
    #             analytics_data[time_key][data.senderId][data.targetId][data.moduleName]['type'] = data.moduleType
    #         if commands:
    #             analytics_data[time_key][data.senderId][data.targetId][data.moduleName]['commands'].append(data.command)
    #         analytics_data[time_key][data.senderId][data.targetId][data.moduleName]['count'] += 1
    #         if data.moduleName not in modules_list:
    #             modules_list.append(data.moduleName)
    #
    #     queried = queried_next
    # j = {'data': analytics_data, 'modules': modules_list, 'timestamp': datetime.now().timestamp(), 'version': 0}
    # if from_to:
    #     j['from'] = from_to[0].timestamp()
    #     j['to'] = from_to[1].timestamp()
    # rnd_path = random_cache_path()
    # with open(f'{rnd_path}.json', 'wb') as f:
    #     f.write(json.dumps(j))
    # with zipfile.ZipFile(f'{rnd_path}.zip', 'w', compression=zipfile.ZIP_DEFLATED) as z:
    #     z.write(f'{rnd_path}.json', 'analytics.json')
    # auth = oss2.Auth(oss_ak, oss_sk)
    # bucket = oss2.Bucket(auth, oss_endpoint, oss_bucket)
    # bucket.put_object_from_file('analytics.zip', f'{rnd_path}.zip')
    # url = bucket.sign_url('GET', 'analytics.zip', expires=expires)
    # if custom_domain := config('oss_custom_domain'):
    #     url = urllib.parse.urlparse(url)
    #     url = f'{url.scheme}://{urllib.parse.urlparse(custom_domain).netloc}{url.path}?{url.query}'
    # return url
    ...
