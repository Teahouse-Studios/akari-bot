import re

from core.builtins import Bot, Image, Url, I18NContext
from core.component import module
from .bugtracker import bugtracker_get, make_screenshot

bug = module("bugtracker", alias="bug", developers=["OasisAkari"], doc=True)


async def query_bugtracker(msg: Bot.MessageSession, mojiraid: str):
    result = await bugtracker_get(msg, mojiraid)
    msg_list = [result[0]]
    if result[1]:
        msg_list.append(Url(result[1]))
    await msg.send_message(msg_list)
    if result[1]:
        screenshot = await make_screenshot(result[1])
        if screenshot:
            img_chain = []
            for scr in screenshot:
                img_chain.append(Image(scr))
            await msg.send_message(img_chain)


@bug.command("<mojiraid> {{bugtracker.help}}")
async def _(msg: Bot.MessageSession, mojiraid: str):
    if mojiraid:
        q = re.match(r"(.*-\d*)", mojiraid)
        if q:
            await query_bugtracker(msg, mojiraid)
        else:
            await msg.finish(I18NContext("bugtracker.message.invalid_mojira_id"))


@bug.regex(
    r"((?:BDS|MCPE|MCD|MCL|MCLG|REALMS|MC|WEB)-\d+)",
    mode="A",
    flags=re.I,
    desc="{bugtracker.help.regex.desc}",
)
async def _(msg: Bot.MessageSession):

    titles = msg.matched_msg[:5]
    for title in titles:
        if title != "":
            await query_bugtracker(msg, title)
