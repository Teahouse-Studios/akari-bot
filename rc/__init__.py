# -*- coding:utf-8 -*-
import json
import aiohttp
from pbc import main2
import re
from UTC8 import UTC8
async def rc():
    url = 'https://minecraft-zh.gamepedia.com/api.php?action=query&list=recentchanges&rcprop=title|user|timestamp&rctype=edit|new&format=json'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as req:
            if req.status != 200:
                return f"请求发生时错误:{req.status}"
            else:
                text1 = await req.text()
    file = json.loads(text1)
    d = []
    for x in file['query']['recentchanges']:
        d.append(x['title']+' - '+x['user']+' '+UTC8(x['timestamp'],'onlytime'))
    y = await main2(d)
    print(y)
    space = '\n'
    f = re.findall(r'.*\n.*\n.*\n.*\n.*',space.join(y))
    if f[0].find('<吃掉了>')!=-1 or f[0].find('<全部吃掉了>')!=-1:
        return(f[0]+'\n...仅显示前5条内容\n检测到外来信息介入，请前往最近更改查看所有消息。Special:最近更改')
    else:
        return(f[0]+'\n...仅显示前5条内容')