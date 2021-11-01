import aiohttp
import ujson as json
import urllib.parse

from core.dirty_check import check
from modules.utils.UTC8 import UTC8
from modules.utils.action_cn import action
from modules.wiki.wikilib import wikilib
from config import Config


async def rc_qq(wiki_url):
    qq_account = Config("qq_account")
    if wiki_url:
        article_path = await wikilib().get_article_path(wiki_url)
        pageurl = article_path + 'Special:RecentChanges'
        url = wiki_url + '?action=query&list=recentchanges&rcprop=title|user|timestamp|loginfo|comment|redirect|flags|sizes|ids&rclimit=99&rctype=edit|new|log&format=json'
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as req:
                if req.status != 200:
                    return f"请求时发生错误：{req.status}\n错误汇报地址：https://github.com/Teahouse-Studios/bot/issues/new?assignees=OasisAkari&labels=bug&template=5678.md&title="
                else:
                    req_text = await req.text()
        j = json.loads(req_text)
        nodelist = [{
            "type": "node",
            "data": {
                "name": f"最近更改地址",
                "uin": qq_account,
                "content": [
                    {"type": "text", "data": {"text": pageurl}}]
            }
        }]
        rclist = []
        userlist = []
        titlelist = []
        for x in j["query"]["recentchanges"]:
            userlist.append(x['user'])
            titlelist.append(x['title'])
        checked_userlist = await check(*userlist)
        count = 0
        user_checked_map = {}
        for u in checked_userlist:
            user_checked_map[userlist[count]] = u
            count += 1
        checked_titlelist = await check(*titlelist)
        count = 0
        title_checked_map = {}
        for t in checked_titlelist:
            title_checked_map[titlelist[count]] = t
            count += 1

        for x in j["query"]["recentchanges"]:
            t = []
            t.append(f"用户：{user_checked_map[x['user']]}")
            t.append(UTC8(x['timestamp'], 'full'))
            if x['type'] == 'edit':
                count = x['newlen'] - x['oldlen']
                if count > 0:
                    count = f'+{str(count)}'
                else:
                    count = str(count)
                t.append(f"{title_checked_map[x['title']]}（{count}）")
                comment = x['comment']
                if comment == '':
                    comment = '（无摘要内容）'
                t.append(comment)
                t.append(
                    f"{article_path}{urllib.parse.quote(title_checked_map[x['title']])}?oldid={x['old_revid']}&diff={x['revid']}")
            if x['type'] == 'new':
                r = ''
                if 'redirect' in x:
                    r = '（新重定向）'
                t.append(f"{title_checked_map[x['title']]}{r}")
                comment = x['comment']
                if comment == '':
                    comment = '（无摘要内容）'
                t.append(comment)
            if x['type'] == 'log':
                log = x['logaction'] + '了' + title_checked_map[x['title']]
                if x['logtype'] in action:
                    a = action[x['logtype']].get(x['logaction'])
                    if a is not None:
                        log = a % title_checked_map[x['title']]
                t.append(log)
                params = x['logparams']
                if 'durations' in params:
                    t.append('时长：' + params['durations'])
                if 'target_title' in params:
                    t.append('对象页面：' + params['target_title'])
                if x['revid'] != 0:
                    t.append(f"{article_path}{urllib.parse.quote(title_checked_map[x['title']])}")
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
        return nodelist
    else:
        return '未设定起始Wiki。'
