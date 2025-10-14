import orjson

from core.builtins.bot import Bot
from core.builtins.message.internal import Image as BImage, Plain, I18NContext
from core.component import module
from core.constants.path import assets_path
from core.web_render import web_render, SourceOptions

arc_assets_path = assets_path / "modules" / "arcaea"

arc = module(
    "arcaea",
    developers=["OasisAkari"],
    desc="{I18N:arcaea.help.desc}",
    doc=True,
    alias=["a", "arc"],
)


@arc.command("download {{I18N:arcaea.help.download}}")
async def _(msg: Bot.MessageSession):
    url = "https://webapi.lowiro.com/webapi/serve/static/bin/arcaea/apk/"
    resp = await web_render.source(SourceOptions(url=url, raw_text=True))
    if resp:
        load_json = orjson.loads(resp)
        url = load_json.get("value", {}).get("url")
    if url:
        await msg.finish(I18NContext("arcaea.message.download", version=load_json["value"]["version"], url=url))
    else:
        await msg.finish(I18NContext("arcaea.message.get_failed"))


@arc.command("random {{I18N:arcaea.help.random}}")
async def _(msg: Bot.MessageSession):
    url = "https://webapi.lowiro.com/webapi/song/showcase/"
    resp = await web_render.source(SourceOptions(url=url, raw_text=True))
    if resp:
        load_json = orjson.loads(resp)
        value = load_json["value"][0]
        image = arc_assets_path / "jacket" / f"{value["song_id"]}.jpg"
        result = [Plain(value["title"]["en"])]
        if image.exists():
            result.append(BImage(path=image))
        await msg.finish(result)
    else:
        await msg.finish(I18NContext("arcaea.message.get_failed"))


@arc.command(
    "rank free {{I18N:arcaea.help.rank.free}}",
    "rank paid {{I18N:arcaea.help.rank.paid}}"
)
async def _(msg: Bot.MessageSession):
    if msg.parsed_msg.get("free", False):
        url = "https://webapi.lowiro.com/webapi/song/rank/free/"

    else:
        url = "https://webapi.lowiro.com/webapi/song/rank/paid/"
    resp = await web_render.source(SourceOptions(url=url, raw_text=True))
    if resp:
        load_json = orjson.loads(resp)
        r = []
        rank = 0
        for x in load_json["value"]:
            rank += 1
            r.append(f"{rank}. {x["title"]["en"]} ({x["status"]})")
        await msg.finish(r)
    else:
        await msg.finish(I18NContext("arcaea.message.get_failed"))


@arc.command("calc <score> <rating> {{I18N:arcaea.help.calc}}")
async def _(msg: Bot.MessageSession, score: int, rating: float):
    if score >= 10000000:
        ptt = rating + 2
    elif score >= 9800000:
        ptt = rating + 1 + (score - 9800000) / 200000
    else:
        ptt = rating + (score - 9500000) / 300000
    await msg.finish(Plain(round(max(0, ptt), 2)))
