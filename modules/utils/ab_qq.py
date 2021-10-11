import aiohttp
import ujson as json

from core.dirty_check import check
from modules.utils.UTC8 import UTC8
from modules.wiki.wikilib import wikilib
from config import Config


async def ab_qq(wiki_url):
    qq_account = Config("qq_account")
    if wiki_url:
        article_path = await wikilib().get_article_path(wiki_url)
        pageurl = article_path + 'Special:AbuseLog'
        url = wiki_url + '?action=query&list=abuselog&aflprop=user|title|action|result|filter|timestamp&afllimit=99&format=json'
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
                "name": f"滥用过滤器日志地址",
                "uin": qq_account,
                "content": [
                    {"type": "text", "data": {"text": pageurl}}]
            }
        }]
        ablist = []
        userlist = []
        titlelist = []
        for x in j["query"]["abuselog"]:
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
        for x in j["query"]["abuselog"]:
            t = []
            t.append(f"用户：{user_checked_map[x['user']]}")
            t.append(f"过滤器名：{x['filter']}")
            t.append(f"页面标题：{title_checked_map[x['title']]}")
            t.append(f"操作：{x['action']}")
            result = x['result']
            if result == '':
                result = 'pass'
            t.append(f"处理结果：{result}")
            t.append(UTC8(x['timestamp'], 'full'))
            ablist.append('\n'.join(t))
        for x in ablist:
            nodelist.append(
                {
                    "type": "node",
                    "data": {
                        "name": f"滥用过滤器日志",
                        "uin": qq_account,
                        "content": [{"type": "text", "data": {"text": x}}],
                    }
                })
        return nodelist
    else:
        return '未设定起始Wiki。'
