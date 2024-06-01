from config import Config
from core.builtins import MessageSession
from core.dirty_check import check
from core.logger import Logger
from modules.wiki.utils.time import strptime2ts
from modules.wiki.utils.wikilib import WikiLib


async def ab_qq(msg: MessageSession, wiki_url):
    wiki = WikiLib(wiki_url)
    qq_account = int(Config("qq_account", cfg_type = (str, int)))
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
    ablist = []
    userlist = []
    titlelist = []
    for x in query["query"]["abuselog"]:
        if 'title' in x:
            userlist.append(x['user'])
            titlelist.append(x['title'])
    checked_userlist = await check(*userlist)
    user_checked_map = {}
    for u in checked_userlist:
        user_checked = u['content']
        if user_checked.find("<吃掉了>") != -1 or user_checked.find("<全部吃掉了>") != -1:
            user_checked = user_checked.replace("<吃掉了>", msg.locale.t("check.redacted"))
            user_checked = user_checked.replace("<全部吃掉了>", msg.locale.t("check.redacted.all"))
        user_checked_map[u['original']] = user_checked
    checked_titlelist = await check(*titlelist)
    title_checked_map = {}
    for t in checked_titlelist:
        title_checked = t['content']
        if user_checked.find("<吃掉了>") != -1 or user_checked.find("<全部吃掉了>") != -1:
            user_checked = user_checked.replace("<吃掉了>", msg.locale.t("check.redacted"))
            user_checked = user_checked.replace("<全部吃掉了>", msg.locale.t("check.redacted.all"))
        title_checked_map[t['original']] = title_checked
    for x in query["query"]["abuselog"]:
        t = []
        time = msg.ts2strftime(strptime2ts(x['timestamp']), iso=True)
        t.append(time)
        result = 'pass' if not x['result'] else x['result']
        t.append(msg.locale.t("wiki.message.ab.qq.slice",
                                  title=title_checked_map[x['title']],
                                  user=user_checked_map[x['user']],
                                  action=x['action'],
                                  filter_name=x['filter'],
                                  result=result))
        ablist.append('\n'.join(t))
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
