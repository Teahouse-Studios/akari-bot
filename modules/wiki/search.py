import asyncio
import re
from typing import Union

from core.builtins import Bot, I18NContext
from core.logger import Logger
from core.utils.message import isint
from .wiki import wiki, query_pages
from .database.models import WikiTargetInfo
from .utils.wikilib import WikiLib


@wiki.command("search <pagename> {{I18N:wiki.help.search}}")
async def _(msg: Bot.MessageSession, pagename: str):
    await search_pages(msg, pagename)


async def search_pages(
    msg: Bot.MessageSession, title: Union[str, list, tuple], use_prefix: bool = True
):
    target = await WikiTargetInfo.get_by_target_id(msg.target.target_id)
    start_wiki = target.api_link
    interwiki_list = target.interwikis
    headers = target.headers
    prefix = target.prefix
    if not start_wiki:
        await msg.finish(I18NContext("wiki.message.set.not_set", prefix=msg.prefixes[0]))
    if isinstance(title, str):
        title = [title]
    query_task = {start_wiki: {"query": [], "iw_prefix": ""}}
    for t in title:
        if prefix and use_prefix:
            t = prefix + t
        if t[0] == ":":
            if len(t) > 1:
                query_task[start_wiki]["query"].append(t[1:])
        else:
            matched = False
            match_interwiki = re.match(r"^(.*?):(.*)", t)
            if match_interwiki:
                g1 = match_interwiki.group(1)
                g2 = match_interwiki.group(2)
                if g1 in interwiki_list:
                    interwiki_url = interwiki_list[g1]
                    if interwiki_url not in query_task:
                        query_task[interwiki_url] = {"query": [], "iw_prefix": g1}
                    query_task[interwiki_url]["query"].append(g2)
                    matched = True
            if not matched:
                query_task[start_wiki]["query"].append(t)
    Logger.debug(query_task)
    msg_list = []
    wait_msg_list = []
    for q in query_task:
        current_task = query_task[q]
        ready_for_query_pages = current_task["query"] if "query" in current_task else []
        iw_prefix = (
            (current_task["iw_prefix"] + ":") if current_task["iw_prefix"] != "" else ""
        )
        tasks = []
        for rd in ready_for_query_pages:
            tasks.append(asyncio.ensure_future(WikiLib(q, headers).search_page(rd)))
        query = await asyncio.gather(*tasks)
        for result in query:
            for r in result:
                wait_msg_list.append(iw_prefix + r)
    if len(wait_msg_list) != 0:
        msg_list.append(I18NContext("wiki.message.search"))
        i = 0
        for w in wait_msg_list:
            i += 1
            w = f"{i}. {w}"
            msg_list.append(w)
        msg_list.append(I18NContext("wiki.message.search.prompt"))
    else:
        await msg.finish(I18NContext("wiki.message.search.not_found"))
    reply = await msg.wait_reply(msg_list)
    if isint(reply.as_display(text_only=True)):
        reply_number = max(0, int(reply.as_display(text_only=True)) - 1)
        await query_pages(reply, wait_msg_list[reply_number])
    else:
        await msg.finish()
