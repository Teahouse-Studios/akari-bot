import re
import urllib.parse

from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import I18NContext, Plain, Url
from core.dirty_check import check
from core.logger import Logger
from modules.wiki.utils.utils import strptime2ts
from modules.wiki.utils.wikilib import WikiLib, WikiInfo

RC_LIMIT = 10


async def get_rc(msg: Bot.MessageSession, wiki_url, headers=None):
    wiki = WikiLib(wiki_url, headers)
    query = await wiki.get_json(action="query", list="recentchanges",
                                rcprop="title|user|timestamp|loginfo|comment|sizes",
                                rclimit=RC_LIMIT,
                                rctype="edit|new|log",
                                _no_login=not msg.session_info.target_info.target_data.get("use_bot_account", False))
    pageurl = wiki.wiki_info.articlepath.replace("$1", "Special:RecentChanges")
    d = []
    for x in query["query"]["recentchanges"]:
        title = x.get("title", "Unknown")
        user = x.get("user", "Unknown")

        if x["type"] in ["edit", "new"]:
            count = x["newlen"] - x["oldlen"]
            if count > 0:
                count = f"+{str(count)}"
            else:
                count = str(count)
            d.append(f"•{msg.format_time(strptime2ts(x["timestamp"]),
                                         iso=True, timezone=False)} - {title} .. ({count}) .. {user}")
            if x["comment"]:
                comment = str(I18NContext("message.brackets", msg=replace_brackets(x["comment"])))
                d.append(comment)
        if x["type"] == "log":
            if x["logtype"] == x["logaction"]:
                log = msg.session_info.locale.t(f"wiki.message.rc.action.{x["logtype"]}",
                                                user=user,
                                                title=title)
            else:
                log = msg.session_info.locale.t(
                    f"wiki.message.rc.action.{x["logtype"]}.{x["logaction"]}",
                    user=user,
                    title=title)
            if log.find("{I18N:") != -1 and log.find("}") != -1:
                if x["logaction"] == x["logtype"]:
                    log = f"{user} {x["logtype"]} {title}"
                else:
                    log = f"{user} {x["logaction"]} {x["logtype"]} {title}"
            d.append(f"•{msg.format_time(strptime2ts(x["timestamp"]), iso=True, timezone=False)} - {log}")
            params = x["logparams"]
            if "suppressredirect" in params:
                d.append(str(I18NContext("wiki.message.rc.params.suppress_redirect")))
            if "oldgroups" and "newgroups" in params:
                d.append(compare_groups(params["oldgroups"], params["newgroups"]))
            if "oldmodel" and "newmodel" in params:
                d.append(f"{params["oldmodel"]} -> {params["newmodel"]}")
            if "description" in params:
                d.append(params["description"])
            if "duration" in params:
                d.append(str(I18NContext("wiki.message.rc.params.duration")) + params["duration"])
            if "flags" in params:
                d.append(", ".join(params["flags"]))
            if "tag" in params:
                d.append(str(I18NContext("wiki.message.rc.params.tag")) + params["tag"])
            if "target_title" in params:
                d.append(str(I18NContext("wiki.message.rc.params.target_title")) + params["target_title"])
            if x["comment"]:
                comment = str(I18NContext("message.brackets", msg=replace_brackets(x["comment"])))
                d.append(comment)
    y = await check(d, session=msg)

    g = MessageChain.assign(
        [Url(pageurl, use_mm=True if msg.session_info.use_url_manager and not wiki.wiki_info.in_allowlist else False)])
    g += MessageChain.assign([Plain(z["content"]) for z in y])
    g.append(I18NContext("message.collapse", amount=RC_LIMIT))

    st = True
    for z in y:
        if not z["status"]:
            st = False
            break
    if not st:
        g.append(I18NContext("wiki.message.utils.redacted"))
    return g


def compare_groups(old_groups, new_groups):
    added_groups = [group for group in new_groups if group not in old_groups]
    removed_groups = [group for group in old_groups if group not in new_groups]
    added = "+" + ", ".join(map(str, added_groups)) if added_groups else ""
    removed = "-" + ", ".join(map(str, removed_groups)) if removed_groups else ""
    return f"{added} {removed}" if added and removed else f"{added}{removed}"


def replace_brackets(comment):
    comment = re.sub(r"\{\{\{(.*?)\}\}\}", r"{{{\1}}}", comment)
    comment = re.sub(r"\[\[(.*?)\]\]", r"[\1]", comment)
    comment = re.sub(r"\{\{(.*?)\}\}", r"[Template:\1]", comment)
    return comment


async def convert_rc_to_detailed_format(msg: Bot.MessageSession, rc: list, wiki_info: WikiInfo):
    rclist = []
    userlist = []
    titlelist = []
    commentlist = []
    for x in rc:
        if "title" in x:
            titlelist.append(x.get("title"))
        if "user" in x:
            userlist.append(x.get("user"))
        if "comment" in x:
            commentlist.append(replace_brackets(x.get("comment")))
    Logger.debug(userlist)
    userlist = list(set(userlist))
    titlelist = list(set(titlelist))
    commentlist = list(set(commentlist))
    checked_userlist = await check(userlist, session=msg)
    user_checked_map = {}
    text_status = True
    for u in checked_userlist:
        user_checked = u["content"]
        if not u["status"]:
            text_status = False
        user_checked_map[u["original"]] = user_checked
    checked_titlelist = await check(titlelist, session=msg)
    title_checked_map = {}
    for t in checked_titlelist:
        title_checked = t["content"]
        if not t["status"]:
            text_status = False
        title_checked_map[t["original"]] = title_checked
    checked_commentlist = await check(commentlist, session=msg)
    comment_checked_map = {}
    for c in checked_commentlist:
        comment_checked = c["content"]
        if not c["status"]:
            text_status = False
        comment_checked_map[c["original"]] = comment_checked
    for x in rc:
        t = []
        original_user = x.get("user", "Unknown")
        original_title = x.get("title", "Unknown")

        user = user_checked_map.get(original_user, original_user)
        title = title_checked_map.get(original_title, original_title)
        comment = comment_checked_map[replace_brackets(x["comment"])] if x.get("comment") else None

        if x["type"] in ["edit", "categorize"]:
            count = x["newlen"] - x["oldlen"]
            if count > 0:
                count = f"+{str(count)}"
            else:
                count = str(count)
            t.append(f"{title} .. ({count}) .. {user}")
            if comment:
                t.append(comment)
            t.append(
                wiki_info.articlepath.replace(
                    "$1",
                    f"{urllib.parse.quote(title)}?oldid={x["old_revid"]}&diff={x["revid"]}"))
        if x["type"] == "new":
            r = str(
                I18NContext(
                    "message.brackets",
                    msg="{I18N:wiki.message.rc.new_redirect}")) if "redirect" in x else ""
            t.append(f"{title}{r} .. (+{x["newlen"]}) .. {user}")
            if comment:
                t.append(comment)
        if x["type"] == "log":
            if x["logtype"] == x["logaction"]:
                log = msg.session_info.locale.t(f"wiki.message.rc.action.{x["logtype"]}", user=user, title=title)
            else:
                log = msg.session_info.locale.t(
                    f"wiki.message.rc.action.{x["logtype"]}.{x["logaction"]}",
                    user=user,
                    title=title)
            if log.find("{I18N:") != -1 and log.find("}") != -1:
                if x["logtype"] == x["logaction"]:
                    log = f"{user} {x["logtype"]} {title}"
                else:
                    log = f"{user} {x["logaction"]} {x["logtype"]} {title}"
            t.append(log)
            params = x["logparams"]
            if "suppressredirect" in params:
                t.append(str(I18NContext("wiki.message.rc.params.suppress_redirect")))
            if "oldgroups" and "newgroups" in params:
                t.append(compare_groups(params["oldgroups"], params["newgroups"]))
            if "oldmodel" and "newmodel" in params:
                t.append(f"{params["oldmodel"]} -> {params["newmodel"]}")
            if "description" in params:
                t.append(params["description"])
            if "duration" in params:
                t.append(str(I18NContext("wiki.message.rc.params.duration")) + params["duration"])
            if "flags" in params:
                t.append(", ".join(params["flags"]))
            if "tag" in params:
                t.append(str(I18NContext("wiki.message.rc.params.tag")) + params["tag"])
            if "target_title" in params:
                t.append(str(I18NContext("wiki.message.rc.params.target_title")) + params["target_title"])
            if comment:
                t.append(comment)
            if x["revid"] != 0:
                t.append(wiki_info.articlepath.replace(
                    "$1", f"{urllib.parse.quote(title_checked_map[x["title"]])}"))
        time = msg.format_time(strptime2ts(x["timestamp"]), iso=True)
        t.append(time)
        if not text_status:
            if (original_title in title_checked_map and title_checked_map[original_title] != original_title) or \
                (original_user in user_checked_map and user_checked_map[original_user] != original_user) or \
                    (comment and comment_checked_map[replace_brackets(x["comment"])] != replace_brackets(x["comment"])):
                t.append(str(I18NContext("wiki.message.utils.redacted")))
        rclist.append("\n".join(t))
    return rclist
