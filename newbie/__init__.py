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
        print(str(y))
        j = space.join(y)
        f = re.findall(r'.*\n.*\n.*\n.*\n.*',j)
        g = '这是当前的新人列表：\n'+f[0]+'\n...仅显示前5条内容'
        if g.find('<吃掉了>') != -1 or g.find('<全部吃掉了>')!=-1:
            return(g+'\n检测到外来信息介入，请前往日志查看所有消息。Special:日志?type=newusers')
        else:
            return(g)
    except Exception as e:
        return('发生错误：'+str(e))