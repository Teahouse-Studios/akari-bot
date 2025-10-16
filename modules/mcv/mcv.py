import re
from datetime import datetime

import orjson
from google_play_scraper import app as google_play_scraper

from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext
from core.constants import Secret
from core.utils.http import get_url, post_url


async def mcjv(msg: Bot.MessageSession):
    try:
        data = orjson.loads(
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

        message1 = msg.session_info.locale.t(
            "mcv.message.mcv.launcher",
            release=data["latest"]["release"],
            snapshot=data["latest"]["snapshot"],
            release_time=msg.format_time(time_release),
            snapshot_time=msg.format_time(time_snapshot),
        )
    except Exception:  # Probably...
        message1 = msg.session_info.locale.t("mcv.message.mcv.launcher.failed")
    return I18NContext("mcv.message.mcv", launcher_ver=message1)


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
    return (
        (
            f"""{msg.session_info.locale.t("mcv.message.mcbv.play_store")}
{play_store_version if play_store_version else msg.session_info.locale.t("mcv.message.mcbv.get_failed")}
"""
            if Secret.ip_country != "China"
            else ""
        )
        + f"""{msg.session_info.locale.t("mcv.message.mcbv.ms_store")}
{ms_store_version if ms_store_version else msg.session_info.locale.t("mcv.message.mcbv.get_failed")}"""
    )

# async def mcev(msg: Bot.MessageSession):
#     try:
#         data = await get_url(
#             "https://meedownloads.blob.core.windows.net/win32/x86/updates/Updates.txt",
#             200,
#         )
#         Logger.debug(data)
#         version = re.search(r"(?<=\[)(.*?)(?=])", data)[0]
#         Logger.debug(version)
#         return I18NContext("mcv.message.mcev", version=version)
#     except Exception:  # Probably...
#         await msg.finish(I18NContext("mcv.message.error.server"))
