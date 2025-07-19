from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import I18NContext, Plain, Url
from core.builtins.session.internal import MessageSession
from core.dirty_check import check
from modules.wiki.utils.wikilib import WikiLib

NEWBIE_LIMIT = 10


async def get_newbie(wiki_url, headers=None, session: MessageSession = None):
    wiki = WikiLib(wiki_url, headers)
    query = await wiki.get_json(action="query", list="logevents", letype="newusers")
    pageurl = wiki.wiki_info.articlepath.replace("$1", "Special:Log?type=newusers")
    d = []
    for x in query["query"]["logevents"][:NEWBIE_LIMIT]:
        if "title" in x:
            d.append(x["title"])
    y = await check(d, session=session)
    g = MessageChain.assign(
        [Url(pageurl, use_mm=True if session and session.session_info.use_url_manager and not wiki.wiki_info.in_allowlist else False)])
    g += MessageChain.assign([Plain(z["content"]) for z in y])
    g.append(I18NContext("message.collapse", amount=NEWBIE_LIMIT))

    st = True
    for z in y:
        if not z["status"]:
            st = False
            break
    if not st:
        g.append(I18NContext("wiki.message.utils.redacted"))
    return g
