import re

import httpx

from core.builtins import Bot, I18NContext
from core.component import module
from .bili_api import get_video_info

bili = module(
    "bilibili",
    alias="bili",
    developers=["DoroWolf"],
    desc="{bilibili.help.desc}",
    doc=True,
    support_languages=["zh_cn"],
)


@bili.command(
    "<bid> [-i] {{bilibili.help}}",
    options_desc={"-i": "{bilibili.help.option.i}"},
    exclude_from=["Discord|Channel"],
)
@bili.command("<bid> {{bilibili.help}}", available_for=["Discord|Channel"])
async def _(msg: Bot.MessageSession, bid: str, get_detail=False):
    if msg.parsed_msg.get("-i", False):
        get_detail = True
    if bid[:2].upper() == "BV":
        query = f"?bvid={bid}"
    elif bid[:2].upper() == "AV":
        query = f"?aid={bid[2:]}"
    else:
        return await msg.finish(I18NContext("bilibili.message.invalid"))
    output = await get_video_info(msg, query, get_detail)
    await msg.finish(output)


@bili.regex(r"av(\d+)\b", flags=re.I, mode="A", desc="{bilibili.help.regex.av}")
async def _(msg: Bot.MessageSession):
    matched = msg.matched_msg[:5]
    for video in matched:
        if video:
            query = f"?aid={video}"
            output = await get_video_info(msg, query)
            await msg.send_message(output)


@bili.regex(r"BV[a-zA-Z0-9]{10}", mode="A", desc="{bilibili.help.regex.bv}")
async def _(msg: Bot.MessageSession):
    matched = msg.matched_msg[:5]
    for video in matched:
        if video:
            query = f"?bvid={video}"
            output = await get_video_info(msg, query)
            await msg.send_message(output)


@bili.regex(r"(?:http[s]?:\/\/)?(?:bili(?:22|33|2233)\.cn|b23\.tv)\/([A-Za-z0-9]{7})(?:\/.*?|)",
            mode="A",
            desc="{bilibili.help.regex.url}",
            show_typing=False,
            text_only=False
            )
async def _(msg: Bot.MessageSession):
    matched = msg.matched_msg[:5]
    for video in matched:
        if video != "":
            query = await parse_shorturl(f"https://b23.tv/{video}")
            if not query:
                return
            output = await get_video_info(msg, query)
            await msg.send_message(output)


async def parse_shorturl(shorturl):
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(shorturl, follow_redirects=False)
            target_url = resp.headers.get("Location")

        video = re.search(r"/video/([^/?]+)", target_url)
        if video:
            return f"?bvid={video.group(1)}"
        return None
    except Exception:
        return None
