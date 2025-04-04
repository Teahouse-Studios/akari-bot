# https://github.com/XeroAlpha/caidlist/blob/master/backend/API.md
import urllib.parse

from core.builtins import Bot
from core.component import module
from core.utils.http import get_url

API = "https://ca.projectxero.top/idlist/search"
SEARCH_LIMIT = 5

i = module("idlist", doc=True, support_languages=["zh_cn"])


@i.command("<query> {{idlist.help}}")
async def _(msg: Bot.MessageSession, query: str):
    query_options = {"q": query, "limit": f"{SEARCH_LIMIT + 1}"}
    query_url = f"{API}?{urllib.parse.urlencode(query_options)}"
    resp = await get_url(query_url, 200, fmt="json")
    result = resp["data"]["result"]
    plain_texts = []
    if result:
        for x in result[0:SEARCH_LIMIT]:
            v = x["value"].split("\n")[0]
            plain_texts.append(f"{x["enumName"]}：{x["key"]} -> {v}")
        if resp["data"]["count"] > SEARCH_LIMIT:
            plain_texts.append(
                msg.locale.t("message.collapse", amount=SEARCH_LIMIT)
                + msg.locale.t("idlist.message.collapse")
            )
            plain_texts.append(f"https://ca.projectxero.top/idlist/{resp["data"]["hash"]}")
        await msg.finish(plain_texts)
    else:
        await msg.finish(msg.locale.t("idlist.message.none"))
