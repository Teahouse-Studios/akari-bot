from core.builtins.message.chain import MessageChain, MessageNodes
from core.builtins.message.internal import I18NContext, Plain, Url
from core.builtins.session.internal import MessageSession
from modules.wiki.utils.wikilib import WikiLib
from .rc import convert_rc_to_detailed_format


async def get_rc_qq(msg: MessageSession, wiki_url, headers=None):
    wiki = WikiLib(wiki_url, headers)
    query = await wiki.get_json(
        action="query",
        list="recentchanges",
        rcprop="title|user|timestamp|loginfo|comment|redirect|flags|sizes|ids",
        rclimit=99,
        rctype="edit|new|log",
        _no_login=not msg.session_info.target_info.target_data.get("use_bot_account", False),
    )
    wiki_info = wiki.wiki_info
    pageurl = wiki.wiki_info.articlepath.replace("$1", "Special:RecentChanges")
    msgchain_lst = [MessageChain.assign([I18NContext("wiki.message.rc.qq.title"), Url(
        pageurl, use_mm=msg.session_info.use_url_manager and not wiki.wiki_info.in_allowlist)])]
    if wiki.wiki_info.in_allowlist:
        msgchain_lst.append(MessageChain.assign([I18NContext("wiki.message.rc.qq.link.prompt")]))
    rclist = await convert_rc_to_detailed_format(msg, query["query"]["recentchanges"], wiki_info)

    for x in rclist:
        msgchain_lst.append(MessageChain.assign([Plain(x)]))
    nodelist = MessageNodes.assign(msgchain_lst, name=msg.session_info.locale.t("wiki.message.rc.qq.title"))
    return nodelist


def compare_groups(old_groups, new_groups):
    added_groups = [group for group in new_groups if group not in old_groups]
    removed_groups = [group for group in old_groups if group not in new_groups]
    added = "+" + ", ".join(map(str, added_groups)) if added_groups else ""
    removed = "-" + ", ".join(map(str, removed_groups)) if removed_groups else ""
    return f"{added} {removed}" if added and removed else f"{added}{removed}"
