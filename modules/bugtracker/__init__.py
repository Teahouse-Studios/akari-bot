import re

from core.builtins.bot import Bot
from core.builtins.message.internal import Url, I18NContext
from core.component import module
from .bugtracker import bugtracker_get, make_screenshot

bug = module("bugtracker", alias="bug", developers=["OasisAkari"], doc=True)


async def query_bugtracker(msg: Bot.MessageSession, mojiraid: str):
    result = await bugtracker_get(msg, mojiraid)
    msg_list = [result[0]]
    if result[1]:
        msg_list.append(Url(result[1], use_mm=False))
    await msg.send_message(msg_list)
    if result[1]:
        screenshot = await make_screenshot(result[1])
        if screenshot:
            await msg.send_message(screenshot)


@bug.command("<mojiraid> {{I18N:bugtracker.help}}")
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
    desc="{I18N:bugtracker.help.regex.desc}",
)
async def _(msg: Bot.MessageSession):
    titles = msg.matched_msg[:5]
    for title in titles:
        if title != "":
            await query_bugtracker(msg, title)
