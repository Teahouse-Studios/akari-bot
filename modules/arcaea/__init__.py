import os

from core.builtins import Bot, Image as BImage, Plain, I18NContext
from core.component import module
from core.constants.path import assets_path
from core.utils.http import get_url
from core.utils.web_render import webrender

arc_assets_path = os.path.join(assets_path, "modules", "arcaea")


arc = module(
    "arcaea",
    developers=["OasisAkari"],
    desc="{arcaea.help.desc}",
    doc=True,
    alias=["a", "arc"],
)


@arc.command("download {{arcaea.help.download}}")
async def _(msg: Bot.MessageSession):
    url = "https://webapi.lowiro.com/webapi/serve/static/bin/arcaea/apk/"
    resp = await get_url(
        webrender("source", url), 200, fmt="json", request_private_ip=True
    )
    if resp:
        url = resp.get("value", {}).get("url")
    if url:
        await msg.finish(I18NContext("arcaea.message.download", version=resp["value"]["version"], url=url))
    else:
        await msg.finish(I18NContext("arcaea.message.get_failed"))


@arc.command("random {{arcaea.help.random}}")
async def _(msg: Bot.MessageSession):
    url = "https://webapi.lowiro.com/webapi/song/showcase/"
    resp = await get_url(
        webrender("source", url), 200, fmt="json", request_private_ip=True
    )
    if resp:
        value = resp["value"][0]
        image = os.path.join(arc_assets_path, "jacket", f"{value["song_id"]}.jpg")
        result = [Plain(value["title"]["en"])]
        if os.path.exists(image):
            result.append(BImage(path=image))
        await msg.finish(result)
    else:
        await msg.finish(I18NContext("arcaea.message.get_failed"))


@arc.command(
    "rank free {{arcaea.help.rank.free}}", "rank paid {{arcaea.help.rank.paid}}"
)
async def _(msg: Bot.MessageSession):
    if msg.parsed_msg.get("free", False):
        url = "https://webapi.lowiro.com/webapi/song/rank/free/"
        resp = await get_url(
            webrender("source", url), 200, fmt="json", request_private_ip=True
        )
    else:
        url = "https://webapi.lowiro.com/webapi/song/rank/paid/"
        resp = await get_url(
            webrender("source", url), 200, fmt="json", request_private_ip=True
        )
    if resp:
        r = []
        rank = 0
        for x in resp["value"]:
            rank += 1
            r.append(f"{rank}. {x["title"]["en"]} ({x["status"]})")
        await msg.finish(r)
    else:
        await msg.finish(I18NContext("arcaea.message.get_failed"))


@arc.command("calc <score> <rating> {{arcaea.help.calc}}")
async def _(msg: Bot.MessageSession, score: int, rating: float):
    if score >= 10000000:
        ptt = rating + 2
    elif score >= 9800000:
        ptt = rating + 1 + (score - 9800000) / 200000
    else:
        ptt = rating + (score - 9500000) / 300000
    await msg.finish(Plain(round(max(0, ptt), 2)))
