import json

import aiohttp

from core.dirty_check import check
from modules.utils.UTC8 import UTC8
from modules.wiki.database import get_start_wiki


async def ab(table, id):
    get_wiki_url = get_start_wiki(table, id)
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
                'filter'] + '\n处理结果：' + x['result'] + '\n')
        y = await check(d)
        if y.find('<吃掉了>') != -1 or y.find('<全部吃掉了>') != -1:
            return y + '\n...仅显示前5条内容\n检测到外来信息介入，请前往滥用日志查看所有消息。Special:滥用日志\n[一分钟后撤回本消息]'
        else:
            return y + '\n...仅显示前5条内容\n[一分钟后撤回本消息]'
    else:
        return '未设定起始Wiki。'
