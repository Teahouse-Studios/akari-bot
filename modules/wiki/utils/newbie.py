from core.builtins import Bot
from core.dirty_check import check
from modules.wiki.utils.wikilib import WikiLib


async def newbie(msg: Bot.MessageSession, wiki_url):
    wiki = WikiLib(wiki_url)
    query = await wiki.get_json(action='query', list='logevents', letype='newusers')
    pageurl = wiki.wiki_info.articlepath.replace(
        '$1', 'Special:Log?type=newusers')
    d = []
    for x in query['query']['logevents'][:5]:
        if 'title' in x:
            d.append(x['title'])
    y = await check(*d)
    y = '\n'.join(z['content'] for z in y)
    g = f'{pageurl}\n{y}\n{msg.locale.t("wiki.message.utils.collapse")}'
    if g.find(msg.locale.t("check.redacted")) != -1 or g.find(msg.locale.t("check.redacted.all")) != -1:
        g += f'\n{msg.locale.t("wiki.message.utils.banned")}'
    return g
