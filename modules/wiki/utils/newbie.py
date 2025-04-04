from core.builtins import Bot
from core.dirty_check import check
from modules.wiki.utils.wikilib import WikiLib

NEWBIE_LIMIT = 10


async def newbie(msg: Bot.MessageSession, wiki_url):
    wiki = WikiLib(wiki_url)
    query = await wiki.get_json(action="query", list="logevents", letype="newusers")
    pageurl = wiki.wiki_info.articlepath.replace("$1", "Special:Log?type=newusers")
    d = []
    for x in query["query"]["logevents"][:NEWBIE_LIMIT]:
        if "title" in x:
            d.append(x["title"])
    y = await check(*d)
    yy = "\n".join(z["content"] for z in y)
    g = f"{pageurl}\n{yy}\n{msg.locale.t("message.collapse", amount=NEWBIE_LIMIT)}"
    st = True
    for z in y:
        if not z["status"]:
            st = False
            break
    if not st:
        g += f"\n{msg.locale.t("wiki.message.utils.redacted")}"
    return g
