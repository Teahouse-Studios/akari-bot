import re
import traceback
from datetime import datetime

import orjson as json
from bs4 import BeautifulSoup
from google_play_scraper import app as google_play_scraper

from core.builtins import I18NContext, FormattedTime, MessageChain
from core.config import Config
from core.constants.info import Secret
from core.logger import Logger
from core.queue import JobQueue
from core.scheduler import Scheduler, IntervalTrigger
from core.utils.http import get_url
from core.utils.storedata import get_stored_list, update_stored_list
from core.utils.web_render import webrender


async def get_article(version):
    match_snapshot = re.match(r".*?w.*", version)
    link = False
    if match_snapshot:
        link = "https://www.minecraft.net/en-us/article/minecraft-snapshot-" + version
    match_prerelease1 = re.match(r"(.*?)-pre(.*[0-9])", version)
    match_prerelease2 = re.match(r"(.*?) Pre-Release (.*[0-9])", version)
    if match_prerelease1:
        match_prerelease = match_prerelease1
    elif match_prerelease2:
        match_prerelease = match_prerelease2
    else:
        match_prerelease = False
    if match_prerelease:
        link = (
            "https://www.minecraft.net/en-us/article/minecraft-"
            + re.sub("\\.", "-", match_prerelease.group(1))
            + f"-pre-release-{match_prerelease.group(2)}"
        )
    match_release_candidate = re.match(r"(.*?)-rc(.*[0-9])", version)
    if match_release_candidate:
        link = (
            "https://www.minecraft.net/en-us/article/minecraft-"
            + re.sub("\\.", "-", match_release_candidate.group(1))
            + f"-release-candidate-{match_release_candidate.group(2)}"
        )
    if not link:
        link = (
            "https://www.minecraft.net/en-us/article/minecraft-java-edition-"
            + re.sub("\\.", "-", version)
        )

    try:
        html = await get_url(
            webrender("source", link),
            attempt=1,
            request_private_ip=True,
            logging_err_resp=False,
        )

        soup = BeautifulSoup(html, "html.parser")

        title = soup.find("h1")
        if title.text == "WE’RE SSSSSSSORRY":
            return "", ""
        return link, title.text
    except Exception:
        if Config("debug", False):
            Logger.error(traceback.format_exc())
        return "", ""


trigger_times = 60 if not Config("slower_schedule", False) else 180


@Scheduler.scheduled_job(IntervalTrigger(seconds=trigger_times))
async def mcv_rss():
    url = "https://piston-meta.mojang.com/mc/game/version_manifest.json"
    try:
        verlist = await get_stored_list("scheduler", "mcv_rss")
        file = json.loads(await get_url(url, attempt=1, logging_err_resp=False))
        release = file["latest"]["release"]
        snapshot = file["latest"]["snapshot"]
        time_release = 0
        time_snapshot = 0
        for v in file["versions"]:
            if v["id"] == release:
                time_release = datetime.fromisoformat(v["releaseTime"]).timestamp()
            if v["id"] == snapshot:
                time_snapshot = datetime.fromisoformat(v["releaseTime"]).timestamp()

        if release not in verlist:
            Logger.info(f"Huh, we find {release}.")

            await JobQueue.trigger_hook_all(
                "mcv_rss",
                message=MessageChain(
                    [
                        I18NContext("mcv_rss.message.mcv_rss.release", version=release),
                        FormattedTime(time_release),
                    ]
                ),
            )
            verlist.append(release)
            await update_stored_list("scheduler", "mcv_rss", verlist)
            article = await get_article(release)
            if article[0] != "":
                get_stored_news_title = await get_stored_list("scheduler", "mcnews")
                if article[1] not in get_stored_news_title:
                    await JobQueue.trigger_hook_all(
                        "minecraft_news",
                        message=MessageChain(
                            [
                                I18NContext(
                                    "minecraft_news.message.update_log",
                                    version=release,
                                    article=article[0],
                                )
                            ]
                        ),
                    )
                    get_stored_news_title.append(article[1])
                    await update_stored_list("scheduler", "mcnews", get_stored_news_title)
        if snapshot not in verlist:
            Logger.info(f"Huh, we find {snapshot}.")
            await JobQueue.trigger_hook_all(
                "mcv_rss",
                message=MessageChain(
                    [
                        I18NContext(
                            "mcv_rss.message.mcv_rss.snapshot",
                            version=file["latest"]["snapshot"],
                        ),
                        FormattedTime(time_snapshot),
                    ]
                ),
            )
            verlist.append(snapshot)
            await update_stored_list("scheduler", "mcv_rss", verlist)
            article = await get_article(snapshot)
            if article[0] != "":
                get_stored_news_title = await get_stored_list("scheduler", "mcnews")
                if article[1] not in get_stored_news_title:
                    await JobQueue.trigger_hook_all(
                        "minecraft_news",
                        message=MessageChain(
                            [
                                I18NContext(
                                    "minecraft_news.message.update_log",
                                    version=snapshot,
                                    article=article[0],
                                )
                            ]
                        ),
                    )
                    get_stored_news_title.append(article[1])
                    await update_stored_list("scheduler", "mcnews", get_stored_news_title)
    except Exception:
        if Config("debug", False):
            Logger.error(traceback.format_exc())


@Scheduler.scheduled_job(IntervalTrigger(seconds=180))
async def mcbv_rss():
    if Secret.ip_country == "China" or not Secret.ip_country:
        return  # 中国大陆无法访问Google Play商店
    try:
        verlist = await get_stored_list("scheduler", "mcbv_rss")
        version = google_play_scraper("com.mojang.minecraftpe")["version"]
        if version not in verlist:
            Logger.info(f"Huh, we find Bedrock {version}.")
            await JobQueue.trigger_hook_all(
                "mcbv_rss",
                message=MessageChain(
                    [I18NContext("mcv_rss.message.mcbv_rss", version=version)]
                ),
            )
            verlist.append(version)
            await update_stored_list("scheduler", "mcbv_rss", verlist)
    except Exception:
        if Config("debug", False):
            Logger.error(traceback.format_exc())

"""

@Scheduler.scheduled_job(IntervalTrigger(seconds=trigger_times))
async def mcv_jira_rss():
    try:
        url = "https://bugs.mojang.com/rest/api/2/project/10400/versions"
        verlist = await get_stored_list("scheduler", "mcv_jira_rss")
        file = json.loads(await get_url(url, 200, attempt=1, logging_err_resp=False))
        releases = []
        for v in file:
            if not v["archived"]:
                releases.append(v["name"])
            else:
                if v["name"] not in verlist:
                    verlist.append(v["name"])
        for release in releases:
            if release not in verlist:
                Logger.info(f"Huh, we find {release}.")
                if release.lower().find("future version") != -1:
                    await JobQueue.trigger_hook_all(
                        "mcv_jira_rss",
                        message=MessageChain(
                            [
                                I18NContext(
                                    "mcv_rss.message.mcv_jira_rss.future",
                                    version=release,
                                )
                            ]
                        ),
                    )
                else:
                    await JobQueue.trigger_hook_all(
                        "mcv_jira_rss",
                        message=MessageChain(
                            [
                                I18NContext(
                                    "mcv_rss.message.mcv_jira_rss", version=release
                                )
                            ]
                        ),
                    )
                verlist.append(release)
                await update_stored_list("scheduler", "mcv_jira_rss", verlist)

    except Exception:
        if Config("debug", False):
            Logger.error(traceback.format_exc())


@Scheduler.scheduled_job(IntervalTrigger(seconds=trigger_times))
async def mcbv_jira_rss():
    try:
        url = "https://bugs.mojang.com/rest/api/2/project/10200/versions"
        verlist = await get_stored_list("scheduler", "mcbv_jira_rss")
        file = json.loads(await get_url(url, 200, attempt=1, logging_err_resp=False))
        releases = []
        for v in file:
            if not v["archived"]:
                releases.append(v["name"])
            else:
                if v["name"] not in verlist:
                    verlist.append(v["name"])
        for release in releases:
            if release not in verlist:
                Logger.info(f"Huh, we find {release}.")

                await JobQueue.trigger_hook_all(
                    "mcbv_jira_rss",
                    message=MessageChain(
                        [I18NContext("mcv_rss.message.mcbv_jira_rss", version=release)]
                    ),
                )
                verlist.append(release)
                await update_stored_list("scheduler", "mcbv_jira_rss", verlist)
    except Exception:
        if Config("debug", False):
            Logger.error(traceback.format_exc())


@Scheduler.scheduled_job(IntervalTrigger(seconds=trigger_times))
async def mcdv_rss():
    try:
        url = "https://bugs.mojang.com/rest/api/2/project/11901/versions"
        verlist = await get_stored_list("scheduler", "mcdv_rss")
        file = json.loads(await get_url(url, 200, attempt=1, logging_err_resp=False))
        releases = []
        for v in file:
            if not v["archived"]:
                releases.append(v["name"])
            else:
                if v["name"] not in verlist:
                    verlist.append(v["name"])
        for release in releases:
            if release not in verlist:
                Logger.info(f"Huh, we find {release}.")

                await JobQueue.trigger_hook_all(
                    "mcdv_rss",
                    message=MessageChain(
                        [I18NContext("mcv_rss.message.mcdv_rss", version=release)]
                    ),
                )
                verlist.append(release)
                await update_stored_list("scheduler", "mcdv_rss", verlist)
    except Exception:
        if Config("debug", False):
            Logger.error(traceback.format_exc())


@Scheduler.scheduled_job(IntervalTrigger(seconds=trigger_times))
async def mclgv_rss():
    try:
        url = "https://bugs.mojang.com/rest/api/2/project/12200/versions"
        verlist = await get_stored_list("scheduler", "mclgv_rss")
        file = json.loads(await get_url(url, 200, attempt=1, logging_err_resp=False))
        releases = []
        for v in file:
            if not v["archived"]:
                releases.append(v["name"])
            else:
                if v["name"] not in verlist:
                    verlist.append(v["name"])
        for release in releases:
            if release not in verlist:
                Logger.info(f"Huh, we find {release}.")

                await JobQueue.trigger_hook_all(
                    "mclgv_rss",
                    message=MessageChain(
                        [I18NContext("mcv_rss.message.mclgv_rss", version=release)]
                    ),
                )
                verlist.append(release)
                await update_stored_list("scheduler", "mclgv_rss", verlist)
    except Exception:
        if Config("debug", False):
            Logger.error(traceback.format_exc())
"""
