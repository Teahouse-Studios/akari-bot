"""Track Arcaea version updates and push notifications."""

import orjson

from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import I18NContext
from core.component import module
from core.config import Config
from core.logger import Logger
from core.scheduler import IntervalTrigger
from core.utils.http import get_url
from core.utils.storedata import get_stored_list, update_stored_list

trigger_times = 60 if not Config("slower_schedule", False) else 180

arcaea_rss = module(
    "arcaea_rss",
    developers=["SkyEye_FAST"],
    desc="{I18N:arcaea_rss.help.desc}",
    alias=["arc_rss"],
    doc=True,
    rss=True,
)


async def get_latest_version() -> tuple[str, str] | None:
    """Fetch the latest Arcaea APK version and download URL."""
    url = "https://webapi.lowiro.com/webapi/serve/static/bin/arcaea/apk/"
    resp = await get_url(url, attempt=1, logging_err_resp=False)
    if not resp:
        return None

    try:
        load_json = orjson.loads(resp)
        value = load_json.get("value")
        if not isinstance(value, dict):
            return None
        version = value.get("version")
        download_url = value.get("url")
        if not isinstance(version, str) or not isinstance(download_url, str):
            return None
        return version, download_url
    except Exception:
        return None


@arcaea_rss.schedule(IntervalTrigger(seconds=trigger_times))
async def _():
    try:
        result = await get_latest_version()
        if not result:
            return

        version, download_url = result
        verlist = await get_stored_list(Bot, "arcaea_rss")

        if version not in verlist:
            Logger.info(f"Huh, we found Arcaea {version}.")
            await Bot.post_message(
                "arcaea_rss",
                message=MessageChain.assign(
                    [
                        I18NContext(
                            "arcaea_rss.message.updated",
                            version=version,
                            url=download_url,
                        )
                    ]
                ),
            )
            verlist.append(version)
            await update_stored_list(Bot, "arcaea_rss", verlist)
    except Exception:
        if Config("debug", False):
            Logger.exception()
