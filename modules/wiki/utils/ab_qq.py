from core.builtins import MessageSession, MessageChain, Plain
from core.config import Config
from core.logger import Logger
from modules.wiki.utils.ab import convert_ab_to_detailed_format
from modules.wiki.utils.wikilib import WikiLib


async def ab_qq(msg: MessageSession, wiki_url):
    wiki = WikiLib(wiki_url)
    query = await wiki.get_json(
        action="query",
        list="abuselog",
        aflprop="user|title|action|result|filter|timestamp",
        afllimit=99,
        _no_login=not msg.options.get("use_bot_account", False),
    )
    pageurl = wiki.wiki_info.articlepath.replace("$1", "Special:AbuseLog")
    msgchain_lst = [MessageChain([Plain(msg.locale.t("wiki.message.ab.qq.link.title"))]),
                    MessageChain([Plain(pageurl)]),
                    MessageChain([Plain(msg.locale.t("wiki.message.ab.qq.title"))])]
    ablist = await convert_ab_to_detailed_format(query["query"]["abuselog"], msg)
    for x in ablist:
        msgchain_lst.append(MessageChain([Plain(x)]))
    nodelist = await msg.msgchain2nodelist(msgchain_lst)
    Logger.debug(nodelist)
    return nodelist
