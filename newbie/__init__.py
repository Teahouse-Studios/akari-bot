# -*- coding:utf-8 -*-
import json 
import requests
from .pbc import main
import re
async def new():
    try:
        url = 'https://minecraft-zh.gamepedia.com/api.php?action=query&list=logevents&letype=newusers&format=json'
        text1 = requests.get(url,timeout=10)
        file = json.loads(text1.text)
        d = []
        for x in file['query']['logevents']:
            d.append(x['title'])
        print(str(d))
        y = await main(d)
        space = '\n'
        f = re.findall(r'.*\n.*\n.*\n.*\n.*',space.join(y))
        print('这是当前的新人列表：\n'+f[0]+'...仅显示前5条内容')
    except Exception as e:
        return('发生错误：'+str(e))