from core.builtins import Url, Bot
from core.dirty_check import check
from modules.wiki.utils.time import strptime2ts
from modules.wiki.utils.wikilib import WikiLib, WikiInfo


async def ab(msg: Bot.MessageSession, wiki_url):
    wiki = WikiLib(wiki_url)
    query = await wiki.get_json(action='query', list='abuselog', aflprop='user|title|action|result|filter|timestamp',
                                _no_login=not msg.options.get("use_bot_account", False))
    pageurl = wiki.wiki_info.articlepath.replace('$1', 'Special:AbuseLog')
    d = []
    for x in query['query']['abuselog'][:5]:
        if 'title' in x:
            result = 'pass' if not x['result'] else x['result']
            d.append('•' + msg.locale.t("wiki.message.ab.slice",
                                        title=x['title'],
                                        user=x['user'],
                                        time=msg.ts2strftime(strptime2ts(x['timestamp']), iso=True, timezone=False),
                                        action=x['action'],
                                        filter_name=x['filter'],
                                        result=result))
    y = await check(*d)
    y = '\n'.join(z['content'] for z in y)
    if y.find("<吃掉了>") != -1 or y.find("<全部吃掉了>") != -1:
        y = y.replace("<吃掉了>", msg.locale.t("check.redacted"))
        y = y.replace("<全部吃掉了>", msg.locale.t("check.redacted.all"))
        return f'{str(Url(pageurl))}\n{y}\n{msg.locale.t("message.collapse", amount="5")}\n{
            msg.locale.t("wiki.message.utils.redacted")}'
    else:
        return f'{str(Url(pageurl))}\n{y}\n{msg.locale.t("message.collapse", amount="5")}'


async def convert_ab_to_detailed_format(abl: list, wiki_info: WikiInfo, msg: Bot.MessageSession):
    ablist = []
    userlist = []
    titlelist = []
    for x in abl:
        if 'title' in x:
            userlist.append(x['user'])
            titlelist.append(x['title'])
    checked_userlist = await check(*userlist)
    user_checked_map = {}
    for u in checked_userlist:
        user_checked = u['content']
        if user_checked.find("<吃掉了>") != -1 or user_checked.find("<全部吃掉了>") != -1:
            user_checked = user_checked.replace("<吃掉了>", msg.locale.t(
                "check.redacted") + '\n' + wiki_info.articlepath.replace('$1', "Special:AbuseLog"))
            user_checked = user_checked.replace("<全部吃掉了>", msg.locale.t(
                "check.redacted.all") + '\n' + wiki_info.articlepath.replace('$1', "Special:AbuseLog"))
        user_checked_map[u['original']] = user_checked
    checked_titlelist = await check(*titlelist)
    title_checked_map = {}
    for t in checked_titlelist:
        title_checked = t['content']
        if title_checked.find("<吃掉了>") != -1 or title_checked.find("<全部吃掉了>") != -1:
            title_checked = title_checked.replace("<吃掉了>", msg.locale.t(
                "check.redacted") + '\n' + wiki_info.articlepath.replace('$1', "Special:AbuseLog"))
            title_checked = title_checked.replace("<全部吃掉了>", msg.locale.t(
                "check.redacted.all") + '\n' + wiki_info.articlepath.replace('$1', "Special:AbuseLog"))
        title_checked_map[t['original']] = title_checked
    for x in abl:
        if 'title' in x:
            t = []
            result = 'pass' if not x['result'] else x['result']
            t.append(msg.locale.t("wiki.message.ab.qq.slice",
                                  title=title_checked_map[x['title']],
                                  user=user_checked_map[x['user']],
                                  action=x['action'],
                                  filter_name=x['filter'],
                                  result=result))
            time = msg.ts2strftime(strptime2ts(x['timestamp']), iso=True)
            t.append(time)
            ablist.append('\n'.join(t))
    return ablist
