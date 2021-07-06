import json

import aiohttp

from core.dirty_check import check
from modules_o.utils.UTC8 import UTC8
from modules_o.wiki.database import WikiDB
from modules_o.wiki.wikilib import wikilib


async def ab(table, id):
    get_wiki_url = WikiDB.get_start_wiki(table, id)
    pageurl = await wikilib().get_article_path(get_wiki_url) + 'Special:AbuseLog'
    if get_wiki_url:
        url = get_wiki_url + '?action=query&list=abuselog&aflprop=user|title|action|result|filter|timestamp&format=json'
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as req:
                if req.status != 200:
                    return f"请求时发生错误：{req.status}"
                else:
                    text1 = await req.text()
        file = json.loads(text1)
        d = []
        for x in file['query']['abuselog'][:5]:
            d.append('•' + x['title'] + ' - ' + x['user'] + '于' + UTC8(x['timestamp'], 'onlytimenoutc') + '\n过滤器名：' + x[
                'filter'] + '\n处理结果：' + x['result'])
        y = await check('\n'.join(d))
        if y.find('<吃掉了>') != -1 or y.find('<全部吃掉了>') != -1:
            return f'{pageurl}\n{y}\n...仅显示前5条内容\n检测到外来信息介入，请前往滥用日志查看所有消息。'
        else:
            return f'{pageurl}\n{y}\n...仅显示前5条内容'
    else:
        return '未设定起始Wiki。'
