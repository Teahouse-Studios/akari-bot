from core.builtins.session.internal import MessageSession
from core.builtins.message.chain import MessageChain, MessageNodes
from core.builtins.message.internal import I18NContext, Plain, Url
from modules.wiki.utils.ab import convert_ab_to_detailed_format
from core.logger import Logger
from modules.wiki.utils.wikilib import WikiLib
from .ab import convert_ab_to_detailed_format


async def get_ab_qq(msg: MessageSession, wiki_url, headers=None):
    wiki = WikiLib(wiki_url, headers)
    query = await wiki.get_json(
        action="query",
        list="abuselog",
        aflprop="user|title|action|result|filter|timestamp",
        afllimit=99,
        _no_login=not msg.session_info.target_info.target_data.get("use_bot_account", False),
    )
    pageurl = wiki.wiki_info.articlepath.replace("$1", "Special:AbuseLog")
    msgchain_lst = [MessageChain([I18NContext("wiki.message.ab.qq.title"), Url(pageurl)])]
    ablist = await convert_ab_to_detailed_format(msg, query["query"]["abuselog"])
    for x in ablist:
        msgchain_lst.append(MessageChain.assign([Plain(x)]))
    nodelist = MessageNodes.assign(msgchain_lst, name=msg.session_info.locale.t("wiki.message.ab.qq.title"))
    return nodelist
