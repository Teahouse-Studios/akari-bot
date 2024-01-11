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
    qq_account = Config("qq_account")
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
            "name": f"最近更改地址",
            "uin": qq_account,
            "content": [
                {"type": "text", "data": {"text": pageurl.replace("$1", 'Special:RecentChanges') +
                                          ('\n tips：复制粘贴下面的任一消息到聊天窗口发送可获取此次改动详细信息的截图。'
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
        user_checked_map[u['original']] = u['content']
    checked_titlelist = await check(*titlelist)
    title_checked_map = {}
    for t in checked_titlelist:
        title_checked_map[t['original']] = t['content']
    for x in query["query"]["recentchanges"]:
        t = []
        t.append(f"用户：{user_checked_map[x['user']]}")
        t.append(msg.ts2strftime(strptime2ts(x['timestamp'])))
        if x['type'] == 'edit':
            count = x['newlen'] - x['oldlen']
            if count > 0:
                count = f'+{str(count)}'
            else:
                count = str(count)
            t.append(f"{title_checked_map[x['title']]}（{count}）")
            comment = x['comment']
            if not comment:
                comment = '（无摘要内容）'
            t.append(comment)
            t.append(
                pageurl.replace(
                    '$1',
                    f"{urllib.parse.quote(title_checked_map[x['title']])}?oldid={x['old_revid']}&diff={x['revid']}"))
        if x['type'] == 'new':
            r = ''
            if 'redirect' in x:
                r = '（新重定向）'
            t.append(f"{title_checked_map[x['title']]}{r}")
            comment = x['comment']
            if not comment:
                comment = '（无摘要内容）'
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
                    "name": f"最近更改",
                    "uin": qq_account,
                    "content": [{"type": "text", "data": {"text": x}}],
                }
            })
    Logger.debug(nodelist)
    return nodelist
