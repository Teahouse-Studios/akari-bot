from core.builtins import Url, Bot
from core.dirty_check import check
from modules.wiki.utils.time import strptime2ts
from modules.wiki.utils.wikilib import WikiLib


async def rc(msg: Bot.MessageSession, wiki_url, count):
    count = 5 if count < 1 else count
    wiki = WikiLib(wiki_url)
    query = await wiki.get_json(action='query', list='recentchanges', rcprop='title|user|timestamp', rctype='edit')
    pageurl = wiki.wiki_info.articlepath.replace('$1', 'Special:RecentChanges')
    d = []
    for x in query['query']['recentchanges'][:count]:
        if 'title' in x:
            d.append(x['title'] + ' - ' + x['user'] +
                     ' ' + msg.ts2strftime(strptime2ts(x['timestamp']), date=False, timezone=False))
    y = await check(*d)
    y = '\n'.join(z['content'] for z in y)
    if y.find("<吃掉了>") != -1 or y.find("<全部吃掉了>") != -1:
        y = y.replace("<吃掉了>", msg.locale.t("check.redacted"))
        y = y.replace("<全部吃掉了>", msg.locale.t("check.redacted.all"))
        msg = f'{str(Url(pageurl))}\n{y}\n{msg.locale.t("message.collapse", amount=str(count))}\n{msg.locale.t("wiki.message.utils.banned")}'
    else:
        msg = f'{str(Url(pageurl))}\n{y}\n{msg.locale.t("message.collapse", amount=str(count))}'
    return msg
