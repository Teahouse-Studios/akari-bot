# -*- coding:utf-8 -*-
import json

import aiohttp

from modules.UTC8 import UTC8
from modules.pbc import pbc


async def ab():
    url = 'https://minecraft-zh.gamepedia.com/api.php?action=query&list=abuselog&aflprop=user|title|action|result|filter|timestamp&format=json'
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as req:
            if req.status != 200:
                return f"请求时发生错误：{req.status}"
            else:
                text1 = await req.text()
    file = json.loads(text1)
    d = []
    for x in file['query']['abuselog'][:5]:
        d.append('•' + x['title'] + ' - ' + x['user'] + '于' + UTC8(x['timestamp'], 'onlytimenoutc') + '\n过滤器名：' + x[
            'filter'] + '\n处理结果：' + x['result'])
    y = await pbc(d)
    space = '\n'
    f = space.join(y)
    if f.find('<吃掉了>') != -1 or f.find('<全部吃掉了>') != -1:
        return f + '\n...仅显示前5条内容\n检测到外来信息介入，请前往滥用日志查看所有消息。Special:滥用日志\n[一分钟后撤回本消息]'
    else:
        return f + '\n...仅显示前5条内容\n[一分钟后撤回本消息]'
