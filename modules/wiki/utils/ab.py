from core.builtins import Url, Bot
from core.dirty_check import check
from modules.wiki.utils.UTC8 import UTC8
from modules.wiki.utils.wikilib import WikiLib


async def ab(msg: Bot.MessageSession, wiki_url):
    wiki = WikiLib(wiki_url)
    query = await wiki.get_json(action='query', list='abuselog', aflprop='user|title|action|result|filter|timestamp')
    pageurl = wiki.wiki_info.articlepath.replace('$1', 'Special:AbuseLog')
    d = []
    for x in query['query']['abuselog'][:5]:
        if 'title' in x:
            d.append(msg.locale.t("wiki.message.ab.slice", title=x['title'], user=x['user'],
                                  time=UTC8(x['timestamp'], 'onlytimenoutc'),
                                  filter_name=x['filter'], result=x['result']))
    y = await check(*d)
    y = '\n'.join(z['content'] for z in y)
    if y.find(msg.locale.t("check.redacted")) != -1 or y.find(msg.locale.t("check.redacted.all")) != -1:
        return f'{str(Url(pageurl))}\n{y}\n{msg.locale.t("wiki.message.utils.collapse")}\n{msg.locale.t("wiki.message.utils.banned")}'
    else:
        return f'{str(Url(pageurl))}\n{y}\n' + msg.locale.t("wiki.message.utils.collapse")
