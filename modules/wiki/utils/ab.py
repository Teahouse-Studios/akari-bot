from core.builtins import Url, Bot
from core.dirty_check import check
from modules.wiki.utils.time import strptime2ts
from modules.wiki.utils.wikilib import WikiLib


async def ab(msg: Bot.MessageSession, wiki_url):
    wiki = WikiLib(wiki_url)
    query = await wiki.get_json(action='query', list='abuselog', aflprop='user|title|action|result|filter|timestamp',
                                _no_login=not msg.options.get("use_bot_account", False))
    pageurl = wiki.wiki_info.articlepath.replace('$1', 'Special:AbuseLog')
    d = []
    for x in query['query']['abuselog'][:5]:
        if 'title' in x:
            result = 'pass' if not x['result'] else x['result']
            d.append(msg.locale.t("wiki.message.ab.slice",
                                  title=x['title'],
                                  user=x['user'],
                                  time=msg.ts2strftime(strptime2ts(x['timestamp']), date=False, timezone=False),
                                  action=x['action'],
                                  filter_name=x['filter'],
                                  result=result))
    y = await check(*d)
    y = '\n'.join(z['content'] for z in y)
    if y.find("<吃掉了>") != -1 or y.find("<全部吃掉了>") != -1:
        y = y.replace("<吃掉了>", msg.locale.t("check.redacted"))
        y = y.replace("<全部吃掉了>", msg.locale.t("check.redacted.all"))
        return f'{str(Url(pageurl))}\n{y}\n{msg.locale.t("message.collapse", amount="5")}\n{msg.locale.t("wiki.message.utils.redacted")}'
    else:
        return f'{str(Url(pageurl))}\n{y}\n{msg.locale.t("message.collapse", amount="5")}'
