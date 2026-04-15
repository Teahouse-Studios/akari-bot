import re
from datetime import datetime

import orjson
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


SNAPSHOT_PATTERN = re.compile(r"^(?P<major>[\d.]+)-snapshot-?(?P<patch>\d)+$")
OLD_SNAPSHOT_PATTERN = re.compile(r"^(1\d)|(2[0-5])[w|W]\d{2}[A-Fa-f]$")
PRERELEASE_PATTERN = re.compile(r"^(?P<major>[\d.]+)-pre-?(?P<patch>\d)+$")
RELEASE_CANDIDATE_PATTERN = re.compile(r"^(?P<major>[\d.]+)-rc-?(?P<patch>\d)+$")
RELEASE_PATTERN = re.compile(r"^\d{1,2}\.\d+(\.\d+)?$")

CHANGELOG_URL_PREFIX = "https://www.minecraft.net/en-us/article/minecraft"


def get_changelog_url(version: str) -> str | None:
    """Generate changelog url of the given minecraft version id"""
    if m := re.match(SNAPSHOT_PATTERN, version):
        return f"{CHANGELOG_URL_PREFIX}-{m.group('major').replace('.', '-')}{m.group('patch')}"
    if m := re.match(PRERELEASE_PATTERN, version):
        return f"{CHANGELOG_URL_PREFIX}-{m.group('major').replace('.', '-')}-pre-release-{m.group('patch')}"
    if m := re.match(RELEASE_CANDIDATE_PATTERN, version):
        return f"{CHANGELOG_URL_PREFIX}-{m.group('major').replace('.', '-')}-release-candidate-{m.group('patch')}"
    if re.match(RELEASE_PATTERN, version):
        return f"{CHANGELOG_URL_PREFIX}-java-edition-{version.replace('.', '-')}"
    if re.match(OLD_SNAPSHOT_PATTERN, version):
        return f"{CHANGELOG_URL_PREFIX}-snapshot-{version}"
    return None


async def get_article(version):
    link = get_changelog_url(version)
    try:
        if link:
            html = await web_render.source(SourceOptions(url=str(link)))

            soup = BeautifulSoup(html, "html.parser")

            title = soup.find("h1")
            if title and title.text == "404":
                return "", ""
            if title:
                return link, title.text
    except Exception:
        if Config("debug", False):
            Logger.exception()
    return "", ""


trigger_times = 60 if not Config("slower_schedule", False) else 180

startup_mute = [True, True]

mcv_rss = module(
    "mcv_rss",
    developers=["OasisAkari", "Dianliang233"],
    # recommend_modules=["mcv_jira_rss"],
    desc="{I18N:mcv_rss.help.mcv_rss.desc}",
    alias="mcvrss",
    doc=True,
    rss=True,
)

mcbv_rss = module(
    "mcbv_rss",
    developers=["OasisAkari"],
    desc="{I18N:mcv_rss.help.mcbv_rss.desc}",
    alias="mcbvrss",
    doc=True,
    rss=True,
)

# for future use

# mcv_jira_rss = module(
#     "mcv_jira_rss",
#     developers=["OasisAkari", "Dianliang233"],
#     recommend_modules=["mcv_rss"],
#     desc="{I18N:mcv_rss.help.mcv_jira_rss.desc}",
#     alias="mcvjirarss",
#     doc=True,
#     rss=True,
# )
#
#
# @mcv_jira_rss.hook()
# async def _(fetch: Bot, ctx: Bot.ModuleHookContext):
#     await fetch.post_message("mcv_jira_rss", **ctx.args)


@mcv_rss.schedule(IntervalTrigger(seconds=trigger_times))
async def _():
    global startup_mute
    url = "https://piston-meta.mojang.com/mc/game/version_manifest.json"
    try:
        verlist = await get_stored_list(Bot.Info.client_name, "mcv_rss")
        file = orjson.loads(await get_url(url, attempt=1, logging_err_resp=False))
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
            Logger.info(f"Huh, we found {release}.")

            if not startup_mute[0]:
                await Bot.post_message(
                    "mcv_rss",
                    message=MessageChain.assign(
                        [
                            I18NContext(
                                "mcv_rss.message.mcv_rss.release",
                                version=release,
                                record_time=FormattedTime(time_release, iso=True),
                                posted_time=FormattedTime(datetime.now().timestamp(), iso=True),
                            ),
                        ]
                    ),
                )
            verlist.append(release)
            await update_stored_list(Bot.Info.client_name, "mcv_rss", verlist)
            article = await get_article(release)
            if article[0] != "":
                get_stored_news_title = await get_stored_list(Bot.Info.client_name, "mcnews")
                if article[1] not in get_stored_news_title:
                    if not startup_mute[0]:
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
                    await update_stored_list(Bot.Info.client_name, "mcnews", get_stored_news_title)
        if snapshot not in verlist:
            Logger.info(f"Huh, we found {snapshot}.")
            if not startup_mute[0]:
                await Bot.post_message(
                    "mcv_rss",
                    message=MessageChain.assign(
                        [
                            I18NContext(
                                "mcv_rss.message.mcv_rss.snapshot",
                                version=file["latest"]["snapshot"],
                                record_time=FormattedTime(time_snapshot, iso=True),
                                posted_time=FormattedTime(datetime.now().timestamp(), iso=True),
                            ),
                        ]
                    ),
                )
            verlist.append(snapshot)
            await update_stored_list(Bot.Info.client_name, "mcv_rss", verlist)
            article = await get_article(snapshot)
            if article[0] != "":
                get_stored_news_title = await get_stored_list(Bot.Info.client_name, "mcnews")
                if article[1] not in get_stored_news_title:
                    if not startup_mute[0]:
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
                    await update_stored_list(Bot.Info.client_name, "mcnews", get_stored_news_title)
        startup_mute[0] = False
    except Exception:
        if Config("debug", False):
            Logger.exception()


@mcbv_rss.schedule(IntervalTrigger(seconds=180))
async def _():
    global startup_mute
    if Secret.ip_country == "China" or not Secret.ip_country:
        return  # 中国大陆无法访问Google Play商店
    try:
        verlist = await get_stored_list(Bot.Info.client_name, "mcbv_rss")
        version = google_play_scraper("com.mojang.minecraftpe")["version"]
        if version not in verlist:
            Logger.info(f"Huh, we found Bedrock {version}.")
            if not startup_mute[1]:
                await Bot.post_message(
                    "mcbv_rss",
                    message=MessageChain.assign([I18NContext("mcv_rss.message.mcbv_rss", version=version)]),
                )
                verlist.append(version)
            await update_stored_list(Bot.Info.client_name, "mcbv_rss", verlist)
        startup_mute[1] = False
    except Exception:
        if Config("debug", False):
            Logger.exception()
