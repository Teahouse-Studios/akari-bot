from core.builtins import MessageChain, Plain, I18NContext, Url
from core.dirty_check import check
from modules.wiki.utils.wikilib import WikiLib

NEWBIE_LIMIT = 10


async def get_newbie(wiki_url, headers=None):
    wiki = WikiLib(wiki_url, headers)
    query = await wiki.get_json(action="query", list="logevents", letype="newusers")
    pageurl = wiki.wiki_info.articlepath.replace("$1", "Special:Log?type=newusers")
    d = []
    for x in query["query"]["logevents"][:NEWBIE_LIMIT]:
        if "title" in x:
            d.append(x["title"])
    y = await check(d)

    g = MessageChain([Url(pageurl)])
    g += MessageChain([Plain(z["content"]) for z in y])
    g.append(I18NContext("message.collapse", amount=NEWBIE_LIMIT))

    st = True
    for z in y:
        if not z["status"]:
            st = False
            break
    if not st:
        g.append(I18NContext("wiki.message.utils.redacted"))
    return g
