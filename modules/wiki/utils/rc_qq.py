import urllib.parse

from config import Config
from core.dirty_check import check
from core.logger import Logger
from modules.wiki.utils.time import strptime2ts
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
        if title_checked.find("<吃掉了>") != -1 or title_checked.find("<全部吃掉了>") != -1:
            title_checked = title_checked.replace("<吃掉了>", msg.locale.t("check.redacted"))
            title_checked = title_checked.replace("<全部吃掉了>", msg.locale.t("check.redacted.all"))
        title_checked_map[t['original']] = title_checked
    for x in query["query"]["recentchanges"]:
        t = []
        user = user_checked_map[x['user']]
        title = title_checked_map[x['title']]
        time = msg.ts2strftime(strptime2ts(x['timestamp']), iso=True)
        t.append(time)
        if x['type'] == 'edit':
            count = x['newlen'] - x['oldlen']
            if count > 0:
                count = f'+{str(count)}'
            else:
                count = str(count)
            t.append(f"{title} .. ({count}) .. {user}")
            if x['comment']:
                comment = x['comment']
                t.append(comment)
            t.append(
                pageurl.replace(
                    '$1',
                    f"{urllib.parse.quote(title)}?oldid={x['old_revid']}&diff={x['revid']}"))
        if x['type'] == 'new':
            r = msg.locale.t('message.brackets', msg=msg.locale.t('wiki.message.rc.new_redirect')) if 'redirect' in x else ''
            t.append(f"{title}{r} .. (+{x['newlen']}) .. {user}")
            if x['comment']:
                comment = x['comment']
                t.append(comment)
        if x['type'] == 'log':
            try:
                if x['logtype'] == x['logaction'] or x['logaction'] == '*':
                    log = msg.locale.t(f"wiki.message.rc.action.{x['logtype']}", user=user, title=title)
                else:
                    log = msg.locale.t(f"wiki.message.rc.action.{x['logtype']}.{x['logaction']}", user=user, title=title)
            except:
                log = f"{user} {x['logaction']} {title}"
            t.append(log)
            params = x['logparams']
            if 'durations' in params:
                t.append(msg.locale.t('wiki.message.rc.qq.durations') + params['durations'])
            if 'target_title' in params:
                t.append(msg.locale.t('wiki.message.rc.qq.target_title') + params['target_title'])
            if x['comment']:
                comment = x['comment']
                t.append(comment)
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
