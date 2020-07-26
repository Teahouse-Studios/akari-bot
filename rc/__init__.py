# -*- coding:utf-8 -*-
import json
import requests
from .pbc import main
import re
async def rc():
    url = 'https://minecraft-zh.gamepedia.com/api.php?action=query&list=recentchanges&rcprop=title|user|timestamp&rctype=edit|new&format=json'
    text1 = requests.get(url,timeout=10)
    file = json.loads(text1.text)
    d = []
    for x in file['query']['recentchanges']:
        d.append(x['title']+' - '+x['user']+' '+x['timestamp'])
    y = await main(d)
    space = '\n'
    f = re.findall(r'.*\n.*\n.*\n.*\n.*',space.join(y))
    return(f[0]+'\n...仅显示前5条内容')