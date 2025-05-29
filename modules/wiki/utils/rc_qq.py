from core.builtins import MessageSession, MessageChain, I18NContext, Plain, Url
from core.logger import Logger
from modules.wiki.utils.wikilib import WikiLib
from .rc import convert_rc_to_detailed_format


async def rc_qq(msg: MessageSession, wiki_url, headers=None):
    wiki = WikiLib(wiki_url, headers)
    query = await wiki.get_json(
        action="query",
        list="recentchanges",
        rcprop="title|user|timestamp|loginfo|comment|redirect|flags|sizes|ids",
        rclimit=99,
        rctype="edit|new|log",
        _no_login=not msg.target_data.get("use_bot_account", False),
    )
    wiki_info = wiki.wiki_info
    pageurl = wiki.wiki_info.articlepath.replace("$1", "Special:RecentChanges")
    msgchain_lst = [
        MessageChain([I18NContext("wiki.message.rc.qq.title"), Url(pageurl)])
    ]
    if wiki.wiki_info.in_allowlist:
        msgchain_lst.append(MessageChain([I18NContext("wiki.message.rc.qq.link.prompt")]))
    rclist = await convert_rc_to_detailed_format(
        query["query"]["recentchanges"], wiki_info, msg
    )

    for x in rclist:
        msgchain_lst.append(MessageChain([Plain(x)]))
    nodelist = await msg.msgchain2nodelist(msgchain_lst)
    Logger.debug(nodelist)
    return nodelist


def compare_groups(old_groups, new_groups):
    added_groups = [group for group in new_groups if group not in old_groups]
    removed_groups = [group for group in old_groups if group not in new_groups]
    added = "+" + ", ".join(map(str, added_groups)) if added_groups else ""
    removed = "-" + ", ".join(map(str, removed_groups)) if removed_groups else ""
    return f"{added} {removed}" if added and removed else f"{added}{removed}"
