import urllib.parse

from config import Config
from core.dirty_check import check
from core.logger import Logger
from modules.wiki.utils.time import strptime2ts
from modules.wiki.utils.action_cn import action
from modules.wiki.utils.wikilib import WikiLib
from core.builtins import MessageSession


async def rc_qq(msg: MessageSession, wiki_url):
    wiki = WikiLib(wiki_url)
    qq_account = int(Config("qq_account", cfg_type = (int, str)))
    query = await wiki.get_json(action='query', list='recentchanges',
                                rcprop='title|user|timestamp|loginfo|comment|redirect|flags|sizes|ids',
                                rclimit=99,
                                rctype='edit|new|log',
                                _no_login=not msg.options.get("use_bot_account", False)
                                )
    pageurl = wiki.wiki_info.articlepath

    nodelist = [{
        "type": "node",
        "data": {
            "name": msg.locale.t('wiki.message.rc.qq.link.title'),
            "uin": qq_account,
            "content": [
                {"type": "text", "data": {"text": pageurl.replace("$1", 'Special:RecentChanges') +
                                          ('\n' + msg.locale.t('wiki.message.rc.qq.link.prompt')
                                           if wiki.wiki_info.in_allowlist else '')}}]
        }
    }]
    rclist = []
    userlist = []
    titlelist = []
    for x in query["query"]["recentchanges"]:
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
    for x in query["query"]["recentchanges"]:
        t = []
        user = user_checked_map[x['user']]
        time = msg.ts2strftime(strptime2ts(x['timestamp']), iso=True)
        t.append(time)
        if x['type'] == 'edit':
            count = x['newlen'] - x['oldlen']
            if count > 0:
                count = f'+{str(count)}'
            else:
                count = str(count)
            t.append(f"{title_checked_map[x['title']]} .. ({count}) .. {user}")
            comment = x['comment'] if x['comment'] else msg.locale.t('wiki.message.rc.no_summary')
            t.append(comment)
            t.append(
                pageurl.replace(
                    '$1',
                    f"{urllib.parse.quote(title_checked_map[x['title']])}?oldid={x['old_revid']}&diff={x['revid']}"))
        if x['type'] == 'new':
            r = msg.locale.t('message.brackets', msg=msg.locale.t('wiki.message.rc.redirect')) if 'redirect' in x else ''
            t.append(f"{title_checked_map[x['title']]}{r} .. (+{x['newlen']}) .. {user}")
            comment = x['comment'] if x['comment'] else msg.locale.t('wiki.message.rc.no_summary')
            t.append(comment)

        if x['type'] == 'log':
            log = x['logaction'] + '了' + title_checked_map[x['title']]
            if x['logtype'] in action:
                a = action[x['logtype']].get(x['logaction'])
                if a:
                    log = a % title_checked_map[x['title']]
            t.append(log)
            params = x['logparams']
            if 'durations' in params:
                t.append('时长：' + params['durations'])
            if 'target_title' in params:
                t.append('对象页面：' + params['target_title'])
            if x['revid'] != 0:
                t.append(pageurl.replace(
                    "$1", f"{urllib.parse.quote(title_checked_map[x['title']])}"))
        rclist.append('\n'.join(t))
    for x in rclist:
        nodelist.append(
            {
                "type": "node",
                "data": {
                    "name": msg.locale.t('wiki.message.rc.qq.title'),
                    "uin": qq_account,
                    "content": [{"type": "text", "data": {"text": x}}],
                }
            })
    Logger.debug(nodelist)
    return nodelist
