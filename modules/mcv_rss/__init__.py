import re
from datetime import datetime

import orjson as json
from bs4 import BeautifulSoup
from google_play_scraper import app as google_play_scraper

from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import I18NContext, FormattedTime
from core.component import module
from core.config import Config
from core.constants import Secret
from core.logger import Logger
from core.scheduler import IntervalTrigger
from core.utils.http import get_url
from core.utils.storedata import get_stored_list, update_stored_list
from core.web_render import web_render, SourceOptions

mcv_rss = module(
    "mcv_rss",
    developers=["OasisAkari", "Dianliang233"],
    recommend_modules=["mcv_jira_rss"],
    desc="{I18N:mcv_rss.help.mcv_rss.desc}",
    alias="mcvrss",
    doc=True,
    rss=True,
)

mcbv_rss = module(
    "mcbv_rss",
    developers=["OasisAkari"],
    recommend_modules=["mcbv_jira_rss"],
    desc="{I18N:mcv_rss.help.mcbv_rss.desc}",
    alias="mcbvrss",
    doc=True,
    rss=True,
)

mcv_jira_rss = module(
    "mcv_jira_rss",
    developers=["OasisAkari", "Dianliang233"],
    recommend_modules=["mcv_rss"],
    desc="{I18N:mcv_rss.help.mcv_jira_rss.desc}",
    alias="mcvjirarss",
    doc=True,
    rss=True,
)


@mcv_jira_rss.hook()
async def _(fetch: Bot, ctx: Bot.ModuleHookContext):
    await fetch.post_message("mcv_jira_rss", **ctx.args)


mcbv_jira_rss = module(
    "mcbv_jira_rss",
    developers=["OasisAkari", "Dianliang233"],
    recommend_modules=["mcbv_rss"],
    desc="{I18N:mcv_rss.help.mcbv_jira_rss.desc}",
    alias="mcbvjirarss",
    doc=True,
    rss=True,
)

mcdv_rss = module(
    "mcdv_rss",
    developers=["OasisAkari", "Dianliang233"],
    desc="{I18N:mcv_rss.help.mcdv_rss.desc}",
    alias=["mcdvrss", "mcdv_rss", "mcdvjirarss"],
    doc=True,
    hidden=True,
    rss=True,
)

mclgv_rss = module(
    "mclgv_rss",
    developers=["OasisAkari", "Dianliang233"],
    desc="{I18N:mcv_rss.help.mclgv_rss.desc}",
    alias=["mclgvrss", "mclgv_rss", "mclgvjirarss"],
    doc=True,
    hidden=True,
    rss=True,
)


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
        if link:
            html = await web_render.source(SourceOptions(url=str(link)))

            soup = BeautifulSoup(html, "html.parser")

            title = soup.find("h1")
            if title.text == "404":
                return "", ""
            return link, title.text
    except Exception:
        if Config("debug", False):
            Logger.exception()
    return "", ""


trigger_times = 60 if not Config("slower_schedule", False) else 180


@mcv_rss.schedule(IntervalTrigger(seconds=trigger_times))
async def _():
    url = "https://piston-meta.mojang.com/mc/game/version_manifest.json"
    try:
        verlist = await get_stored_list(Bot, "mcv_rss")
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

            await Bot.post_message(
                "mcv_rss",
                message=MessageChain.assign(
                    [
                        I18NContext("mcv_rss.message.mcv_rss.release", version=release),
                        FormattedTime(time_release),
                    ]
                ),
            )
            verlist.append(release)
            await update_stored_list(Bot, "mcv_rss", verlist)
            article = await get_article(release)
            if article[0] != "":
                get_stored_news_title = await get_stored_list(Bot, "mcnews")
                if article[1] not in get_stored_news_title:
                    await Bot.post_message(
                        "minecraft_news",
                        message=MessageChain.assign(
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
                    await update_stored_list(Bot, "mcnews", get_stored_news_title)
        if snapshot not in verlist:
            Logger.info(f"Huh, we find {snapshot}.")
            await Bot.post_message(
                "mcv_rss",
                message=MessageChain.assign(
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
            await update_stored_list(Bot, "mcv_rss", verlist)
            article = await get_article(snapshot)
            if article[0] != "":
                get_stored_news_title = await get_stored_list(Bot, "mcnews")
                if article[1] not in get_stored_news_title:
                    await Bot.post_message(
                        "minecraft_news",
                        message=MessageChain.assign(
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
                    await update_stored_list(Bot, "mcnews", get_stored_news_title)
    except Exception:
        if Config("debug", False):
            Logger.exception()


@mcbv_rss.schedule(IntervalTrigger(seconds=180))
async def _():
    if Secret.ip_country == "China" or not Secret.ip_country:
        return  # 中国大陆无法访问Google Play商店
    try:
        verlist = await get_stored_list(Bot, "mcbv_rss")
        version = google_play_scraper("com.mojang.minecraftpe")["version"]
        if version not in verlist:
            Logger.info(f"Huh, we find Bedrock {version}.")
            await Bot.post_message(
                "mcbv_rss",
                message=MessageChain.assign(
                    [I18NContext("mcv_rss.message.mcbv_rss", version=version)]
                ),
            )
            verlist.append(version)
            await update_stored_list(Bot, "mcbv_rss", verlist)
    except Exception:
        if Config("debug", False):
            Logger.exception()


"""

@Scheduler.scheduled_job(IntervalTrigger(seconds=trigger_times))
async def mcv_jira_rss():
    try:
        url = "https://bugs.mojang.com/rest/api/2/project/10400/versions"
        verlist = await get_stored_list(bot, "mcv_jira_rss")
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
                        message=MessageChain.assign(
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
                        message=MessageChain.assign(
                            [
                                I18NContext(
                                    "mcv_rss.message.mcv_jira_rss", version=release
                                )
                            ]
                        ),
                    )
                verlist.append(release)
                await update_stored_list(bot,, "mcv_jira_rss", verlist)

    except Exception:
        if Config("debug", False):
            Logger.exception()


@Scheduler.scheduled_job(IntervalTrigger(seconds=trigger_times))
async def mcbv_jira_rss():
    try:
        url = "https://bugs.mojang.com/rest/api/2/project/10200/versions"
        verlist = await get_stored_list(bot, "mcbv_jira_rss")
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
                    message=MessageChain.assign(
                        [I18NContext("mcv_rss.message.mcbv_jira_rss", version=release)]
                    ),
                )
                verlist.append(release)
                await update_stored_list(bot,, "mcbv_jira_rss", verlist)
    except Exception:
        if Config("debug", False):
            Logger.exception()


@Scheduler.scheduled_job(IntervalTrigger(seconds=trigger_times))
async def mcdv_rss():
    try:
        url = "https://bugs.mojang.com/rest/api/2/project/11901/versions"
        verlist = await get_stored_list(bot, "mcdv_rss")
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
                    message=MessageChain.assign(
                        [I18NContext("mcv_rss.message.mcdv_rss", version=release)]
                    ),
                )
                verlist.append(release)
                await update_stored_list(bot,, "mcdv_rss", verlist)
    except Exception:
        if Config("debug", False):
            Logger.exception()


@Scheduler.scheduled_job(IntervalTrigger(seconds=trigger_times))
async def mclgv_rss():
    try:
        url = "https://bugs.mojang.com/rest/api/2/project/12200/versions"
        verlist = await get_stored_list(bot, "mclgv_rss")
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
                    message=MessageChain.assign(
                        [I18NContext("mcv_rss.message.mclgv_rss", version=release)]
                    ),
                )
                verlist.append(release)
                await update_stored_list(bot,, "mclgv_rss", verlist)
    except Exception:
        if Config("debug", False):
            Logger.exception()
"""
