from core.builtins import Url, Bot
from core.dirty_check import check
from modules.wiki.utils.time import strptime2ts
from modules.wiki.utils.wikilib import WikiLib

AB_LIMIT = 5


async def ab(msg: Bot.MessageSession, wiki_url):
    wiki = WikiLib(wiki_url)
    query = await wiki.get_json(action="query", list="abuselog", aflprop="user|title|action|result|filter|timestamp",
                                _no_login=not msg.target_data.get("use_bot_account", False))
    pageurl = wiki.wiki_info.articlepath.replace("$1", "Special:AbuseLog")
    d = []
    for x in query["query"]["abuselog"][:AB_LIMIT]:
        result = "pass" if not x["result"] else x["result"]
        title = x.get("title", "Unknown")
        user = x.get("user", "Unknown")
        d.append("•" + msg.locale.t("wiki.message.ab.slice",
                                    title=title,
                                    user=user,
                                    time=msg.ts2strftime(strptime2ts(x["timestamp"]), iso=True, timezone=False),
                                    action=x["action"],
                                    filter_name=x["filter"],
                                    result=result))
    y = await check(*d)
    yy = "\n".join(z["content"] for z in y)
    st = True
    for z in y:
        if not z["status"]:
            st = False
            break
    if not st:
        return f"{str(Url(pageurl))}\n{yy}\n{msg.locale.t("message.collapse", amount=AB_LIMIT)}\n{
            msg.locale.t("wiki.message.utils.redacted")}"
    return f"{str(Url(pageurl))}\n{yy}\n{msg.locale.t("message.collapse", amount=AB_LIMIT)}"


async def convert_ab_to_detailed_format(abl: list, msg: Bot.MessageSession):
    ablist = []
    userlist = []
    titlelist = []
    for x in abl:
        if "title" in x:
            titlelist.append(x.get("title"))
        if "user" in x:
            userlist.append(x.get("user"))
    text_status = True
    checked_userlist = await check(*userlist)
    user_checked_map = {}
    for u in checked_userlist:
        if not u["status"]:
            text_status = False
        user_checked = u["content"]
        user_checked_map[u["original"]] = user_checked
    checked_titlelist = await check(*titlelist)
    title_checked_map = {}
    for t in checked_titlelist:
        title_checked = t["content"]
        if not t["status"]:
            text_status = False
        title_checked_map[t["original"]] = title_checked
    for x in abl:
        if "title" in x:
            t = []
            result = "pass" if not x["result"] else x["result"]
            original_title = x.get("title", "Unknown")
            original_user = x.get("user", "Unknown")

            t.append(msg.locale.t("wiki.message.ab.qq.slice",
                                  title=title_checked_map.get(original_title, original_title),
                                  user=user_checked_map.get(original_user, original_user),
                                  action=x["action"],
                                  filter_name=x["filter"],
                                  result=result))
            time = msg.ts2strftime(strptime2ts(x["timestamp"]), iso=True)
            t.append(time)
            if not text_status:
                if (original_title in title_checked_map and title_checked_map[original_title] != original_title) or \
                        (original_user in user_checked_map and user_checked_map[original_user] != original_user):
                    t.append(msg.locale.t("wiki.message.utils.redacted"))
            ablist.append("\n".join(t))
    return ablist
