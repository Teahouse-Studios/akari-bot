from core.dirty_check import check
from modules.wiki.utils.wikilib import WikiLib


async def newbie(wiki_url):
    wiki = WikiLib(wiki_url)
    query = await wiki.get_json(action='query', list='logevents', letype='newusers')
    pageurl = wiki.wiki_info.articlepath.replace(
        '$1', 'Special:Log?type=newusers')
    d = []
    for x in query['query']['logevents'][:5]:
        d.append(x['title'])
    y = await check(*d)
    y = '\n'.join(z['content'] for z in y)
    g = f'{pageurl}\n{y}\n...仅显示前5条内容'
    if g.find('<吃掉了>') != -1 or g.find('<全部吃掉了>') != -1:
        g += '\n检测到外来信息介入，请前往日志查看所有消息。Special:日志?type=newusers'
    return g
