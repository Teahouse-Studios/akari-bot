from core.builtins import Bot
from core.dirty_check import check
from modules.wiki.utils.wikilib import WikiLib


async def newbie(msg: Bot.MessageSession, wiki_url):
    wiki = WikiLib(wiki_url)
    query = await wiki.get_json(action='query', list='logevents', letype='newusers')
    pageurl = wiki.wiki_info.articlepath.replace(
        '$1', 'Special:Log?type=newusers')
    d = []
    for x in query['query']['logevents'][:10]:
        if 'title' in x:
            d.append(x['title'])
    y = await check(*d)
    y = '\n'.join(z['content'] for z in y)
    g = f'{pageurl}\n{y}\n{msg.locale.t("message.collapse", amount="10")}'
    if g.find("<吃掉了>") != -1 or g.find("<全部吃掉了>") != -1:
        g = g.replace("<吃掉了>", msg.locale.t("check.redacted"))
        g = g.replace("<全部吃掉了>", msg.locale.t("check.redacted.all"))
        g += f'\n{msg.locale.t("wiki.message.utils.redacted")}'
    return g
