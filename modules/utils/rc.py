import json

import aiohttp

from core.dirty_check import check
from modules.utils.UTC8 import UTC8
from modules.wiki.database import WikiDB


get_start_wiki = WikiDB().get_start_wiki


async def rc(table, id):
    get_wiki_url = get_start_wiki(table, id)
    if get_wiki_url:
        url = get_wiki_url + '?action=query&list=recentchanges&rcprop=title|user|timestamp&rctype=edit|new&format=json'
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as req:
                if req.status != 200:
                    return f"请求时发生错误：{req.status}"
                else:
                    text1 = await req.text()
        file = json.loads(text1)
        d = []
        for x in file['query']['recentchanges'][:5]:
            d.append(x['title'] + ' - ' + x['user'] + ' ' + UTC8(x['timestamp'], 'onlytime'))
        m = '\n'.join(d)
        print(m)
        y = await check(m)
        print(y)
        if y.find('<吃掉了>') != -1 or y.find('<全部吃掉了>') != -1:
            msg = y + '\n...仅显示前5条内容\n检测到外来信息介入，请前往最近更改查看所有消息。Special:最近更改'
        else:
            msg = y + '\n...仅显示前5条内容'
        return msg
    else:
        return '未设定起始Wiki。'
