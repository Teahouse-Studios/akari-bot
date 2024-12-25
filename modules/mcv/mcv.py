import re
from datetime import datetime

import orjson as json
from google_play_scraper import app as google_play_scraper

from core.builtins import Bot, ErrorMessage
from core.constants.info import Secret
from core.logger import Logger
from core.utils.http import get_url, post_url


async def mcjv(msg: Bot.MessageSession):
    try:
        data = json.loads(
            await get_url(
                "https://piston-meta.mojang.com/mc/game/version_manifest.json", 200
            )
        )
        release = data["latest"]["release"]
        snapshot = data["latest"]["snapshot"]
        time_release = None
        time_snapshot = None
        for v in data["versions"]:
            if v["id"] == release:
                time_release = datetime.fromisoformat(v["releaseTime"]).timestamp()
            if v["id"] == snapshot:
                time_snapshot = datetime.fromisoformat(v["releaseTime"]).timestamp()

        message1 = msg.locale.t(
            "mcv.message.mcv.launcher",
            release=data["latest"]["release"],
            snapshot=data["latest"]["snapshot"],
            release_time=msg.ts2strftime(time_release),
            snapshot_time=msg.ts2strftime(time_snapshot),
        )
    except ConnectionError:  # Probably...
        message1 = msg.locale.t("mcv.message.mcv.launcher.failed")
    try:
        mojira = json.loads(
            await get_url(
                "https://bugs.mojang.com/rest/api/2/project/10400/versions", 200
            )
        )
        release = []
        prefix = " | "
        for v in mojira:
            if not v["archived"]:
                release.append(v["name"])
        message2 = prefix.join(release)
    except Exception:
        message2 = msg.locale.t("mcv.message.mcv.jira.failed")
    return msg.locale.t("mcv.message.mcv", launcher_ver=message1, jira_ver=message2)


async def mcbv(msg: Bot.MessageSession):
    play_store_version = None
    if Secret.ip_country != "China":
        try:  # play store
            play_store_version = google_play_scraper("com.mojang.minecraftpe")[
                "version"
            ]
        except Exception:
            pass
    ms_store_version = None
    try:
        fetch_ = await post_url(
            "https://store.rg-adguard.net/api/GetFiles",
            status_code=200,
            fmt="text",
            data={
                "type": "url",
                "url": "https://www.microsoft.com/store/productId/9NBLGGH2JHXJ",
                "ring": "RP",
                "lang": "zh-CN",
            },
        )
        if fetch_:
            ms_store_version = re.findall(
                r".*Microsoft.MinecraftUWP_(.*?)_.*", fetch_, re.M | re.I
            )[0]
    except Exception:
        pass
    try:
        data = json.loads(
            await get_url(
                "https://bugs.mojang.com/rest/api/2/project/10200/versions", 200
            )
        )
    except ConnectionError:  # Probably...
        return ErrorMessage(
            "{mcv.message.error.server}", locale=msg.locale.locale, enable_report=False
        )
    beta = []
    preview = []
    release = []
    for v in data:
        if not v["archived"]:
            if re.match(r".*Beta$", v["name"]):
                beta.append(v["name"])
            elif re.match(r".*Preview$", v["name"]):
                preview.append(v["name"])
            else:
                if v["name"] != "Future Release":
                    release.append(v["name"])
    fix = " | "
    msg2 = f"Beta: {fix.join(beta)}\nPreview: {fix.join(preview)}\nRelease: {fix.join(release)}"
    return (
        (
            f"""{msg.locale.t("mcv.message.mcbv.play_store")}
{play_store_version if play_store_version else msg.locale.t('mcv.message.mcbv.get_failed')}
"""
            if Secret.ip_country != "China"
            else ""
        )
        + f"""{msg.locale.t("mcv.message.mcbv.ms_store")}
{ms_store_version if ms_store_version else msg.locale.t('mcv.message.mcbv.get_failed')}
"""
        + msg.locale.t("mcv.message.mcbv", jira_ver=msg2)
    )


async def mcdv(msg: Bot.MessageSession):
    try:
        data = json.loads(
            await get_url(
                "https://bugs.mojang.com/rest/api/2/project/11901/versions", 200
            )
        )
    except ConnectionError:  # Probably...
        return ErrorMessage(
            "{mcv.message.error.server}", locale=msg.locale.locale, enable_report=False
        )
    release = []
    for v in data:
        if not v["archived"]:
            release.append(v["name"])
    return msg.locale.t("mcv.message.mcdv", version=" | ".join(release))


async def mcev(msg: Bot.MessageSession):
    try:
        data = await get_url(
            "https://meedownloads.blob.core.windows.net/win32/x86/updates/Updates.txt",
            200,
        )
        Logger.debug(data)
        version = re.search(r"(?<=\[)(.*?)(?=])", data)[0]
        Logger.debug(version)
    except ConnectionError:  # Probably...
        return ErrorMessage(
            "{mcv.message.error.server}", locale=msg.locale.locale, enable_report=False
        )
    return msg.locale.t("mcv.message.mcev", version=version)


async def mclgv(msg: Bot.MessageSession):
    try:
        data = json.loads(
            await get_url(
                "https://bugs.mojang.com/rest/api/2/project/12200/versions", 200
            )
        )
    except ConnectionError:  # Probably...
        return ErrorMessage(
            "{mcv.message.error.server}", locale=msg.locale.locale, enable_report=False
        )
    release = []
    for v in data:
        if not v["archived"]:
            release.append(v["name"])
    return msg.locale.t("mcv.message.mclgv", version=" | ".join(release))
