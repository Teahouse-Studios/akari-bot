# https://github.com/XeroAlpha/caidlist/blob/master/backend/API.md
import urllib.parse

from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext, Plain, Url
from core.component import module
from core.utils.http import get_url

API = "https://idlist.projectxero.top/search"
SEARCH_LIMIT = 5

i = module("idlist", doc=True, support_languages=["zh_cn"])


@i.command("<query> {{I18N:idlist.help}}")
async def _(msg: Bot.MessageSession, query: str):
    query_options = {"q": query, "limit": f"{SEARCH_LIMIT + 1}"}
    query_url = f"{API}?{urllib.parse.urlencode(query_options)}"
    resp = await get_url(query_url, 200, fmt="json")
    result = resp["data"]["result"]
    msgchain = []
    if result:
        for x in result[0:SEARCH_LIMIT]:
            v = x["value"].split("\n")[0]
            msgchain.append(f"{x["enumName"]}：{x["key"]} -> {v}")
        if resp["data"]["count"] > SEARCH_LIMIT:
            msgchain.append(Plain(str(I18NContext("message.collapse", amount=SEARCH_LIMIT)) +
                                  str(I18NContext("idlist.message.collapse"))))
            msgchain.append(Url(f"https://idlist.projectxero.top/{resp["data"]["hash"]}", use_mm=False))
        await msg.finish(msgchain)
    else:
        await msg.finish(I18NContext("idlist.message.none"))
