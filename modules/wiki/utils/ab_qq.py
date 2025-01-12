from core.builtins import MessageSession
from core.config import Config
from core.logger import Logger
from modules.wiki.utils.ab import convert_ab_to_detailed_format
from modules.wiki.utils.wikilib import WikiLib


async def ab_qq(msg: MessageSession, wiki_url):
    wiki = WikiLib(wiki_url)
    qq_account = Config("qq_account", cfg_type=(str, int), table_name="bot_aiocqhttp")
    query = await wiki.get_json(
        action="query",
        list="abuselog",
        aflprop="user|title|action|result|filter|timestamp",
        afllimit=99,
        _no_login=not msg.options.get("use_bot_account", False),
    )
    pageurl = wiki.wiki_info.articlepath.replace("$1", "Special:AbuseLog")
    nodelist = [
        {
            "type": "node",
            "data": {
                "name": msg.locale.t("wiki.message.ab.qq.link.title"),
                "uin": int(qq_account),
                "content": [{"type": "text", "data": {"text": pageurl}}],
            },
        }
    ]

    ablist = await convert_ab_to_detailed_format(query["query"]["abuselog"], msg)
    for x in ablist:
        nodelist.append(
            {
                "type": "node",
                "data": {
                    "name": msg.locale.t("wiki.message.ab.qq.title"),
                    "uin": int(qq_account),
                    "content": [{"type": "text", "data": {"text": x}}],
                },
            }
        )
    Logger.debug(nodelist)
    return nodelist
