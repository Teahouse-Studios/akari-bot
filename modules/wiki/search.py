import re
import urllib.parse

from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import ButtonFrame, I18NContext, Plain, Url
from core.logger import Logger
from core.utils.button import build_button_rows
from core.utils.func import is_int
from .database.models import WikiTargetInfo
from .utils.recommend import finish_with_start_wiki_not_set
from .utils.wikilib import BlockedWikiError, InvalidWikiError, WikiLib
from .wiki import finish_if_wiki_blocked, wiki, query_pages

MAX_SEARCH_RESULTS = 5


@wiki.command("search <pagename> {{I18N:wiki.help.search}}")
async def _(msg: Bot.MessageSession, pagename: str):
    await search_pages(msg, pagename)


async def search_pages(msg: Bot.MessageSession, title: str | list | tuple, use_prefix: bool = True):
    target = await WikiTargetInfo.get_by_target_id(msg.session_info.target_id)
    start_wiki = target.api_link
    interwiki_list = target.interwikis
    headers = target.headers
    prefix = target.prefix
    if not start_wiki:
        await finish_with_start_wiki_not_set(msg)
    await finish_if_wiki_blocked(msg, start_wiki)
    if isinstance(title, str):
        title = [title]
    query_task = {start_wiki: {"query": [], "iw_prefix": ""}}
    for t in title:
        if prefix and use_prefix:
            t = prefix + t
        if not t:
            continue
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
    choices = []
    button_list = []
    search_links = []
    error_message = None
    for q in query_task:
        await finish_if_wiki_blocked(msg, q)
        current_task = query_task[q]
        ready_for_query_pages = current_task["query"] if "query" in current_task else []
        iw_prefix = (current_task["iw_prefix"] + ":") if current_task["iw_prefix"] != "" else ""
        site = WikiLib(q, headers)
        for rd in ready_for_query_pages:
            try:
                result = await site.search_page(rd)
            except BlockedWikiError as e:
                await finish_if_wiki_blocked(msg, e.url)
                raise
            except Exception as e:
                Logger.error(f"Wiki search failed: {e}")
                error_message = (
                    Plain(str(e)) if isinstance(e, InvalidWikiError) else I18NContext("wiki.message.error.query")
                )
                continue
            if site.search_link:
                search_links.append(site.search_link)
            elif site.wiki_info.script:
                search_url = (
                    site.wiki_info.script + "?" + urllib.parse.urlencode({"title": "Special:Search", "search": rd})
                )
                search_links.append(Url(search_url, trusted=True if site.wiki_info.is_allowed else None))
            for r in result:
                wait_msg_list.append(iw_prefix + r)
                choices.append((r, q))

    if len(wait_msg_list) != 0:
        has_more = len(wait_msg_list) > MAX_SEARCH_RESULTS
        wait_msg_list = wait_msg_list[:MAX_SEARCH_RESULTS]
        choices = choices[:MAX_SEARCH_RESULTS]
        msg_list.append(I18NContext("wiki.message.search"))
        i = 0
        if not msg.session_info.support_button:
            for w in wait_msg_list:
                i += 1
                msg_list.append(Plain(f"{i}. {w}"))
            msg_list.append(I18NContext("wiki.message.search.prompt"))
        else:
            msg_list.append(I18NContext("wiki.message.search.prompt.button"))
            for w in wait_msg_list:
                i += 1
                button_list.append({f"{i}. {w}": str(i)})
        if has_more and search_links:
            msg_list.append(I18NContext("wiki.message.search.more", url=MessageChain.assign(search_links[:3])))
        if error_message:
            msg_list.append(error_message)
    else:
        await msg.finish(error_message or I18NContext("wiki.message.search.not_found"))

    async def _callback(msg: Bot.MessageSession):
        if is_int(msg.as_display(text_only=True)):
            reply_number = int(msg.as_display(text_only=True)) - 1
            if 0 <= reply_number < len(choices):
                selected_title, api = choices[reply_number]
                await query_pages(msg, selected_title, start_wiki_api=api, use_prefix=False)
            else:
                await msg.finish()

    if button_list:
        msg_list.append(ButtonFrame(build_button_rows(button_list)))
    await msg.send_message(msg_list, callback=_callback)
