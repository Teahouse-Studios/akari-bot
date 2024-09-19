from config import Config
from core.builtins import MessageSession
from core.dirty_check import check
from core.logger import Logger
from modules.wiki.utils.time import strptime2ts
from modules.wiki.utils.wikilib import WikiLib
from .ab import convert_ab_to_detailed_format


async def ab_qq(msg: MessageSession, wiki_url):
    wiki = WikiLib(wiki_url)
    qq_account = int(Config("qq_account", cfg_type=(str, int)))
    query = await wiki.get_json(action='query', list='abuselog', aflprop='user|title|action|result|filter|timestamp',
                                afllimit=99, _no_login=not msg.options.get("use_bot_account", False))
    pageurl = wiki.wiki_info.articlepath.replace("$1", 'Special:AbuseLog')
    nodelist = [{
        "type": "node",
        "data": {
            "name": msg.locale.t('wiki.message.ab.qq.link.title'),
            "uin": qq_account,
            "content": [
                {"type": "text", "data": {"text": pageurl}}]
        }
    }]

    ablist = await convert_ab_to_detailed_format(query["query"]["abuselog"], wiki.wiki_info, msg)
    for x in ablist:
        nodelist.append(
            {
                "type": "node",
                "data": {
                    "name": msg.locale.t('wiki.message.ab.qq.title'),
                    "uin": qq_account,
                    "content": [{"type": "text", "data": {"text": x}}],
                }
            })
    Logger.debug(nodelist)
    return nodelist
