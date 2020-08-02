# -*- coding:utf-8 -*-
import json
import requests
from pbc import main
import re
async def ab():
    url = 'https://minecraft-zh.gamepedia.com/api.php?action=query&list=abuselog&aflprop=user|title|action|result|filter&format=json'
    text1 = requests.get(url,timeout=10)
    file = json.loads(text1.text)
    d = []
    for x in file['query']['abuselog']:
        d.append(x['title']+' - '+x['user']+'\n处理结果：'+x['result'])
    y = await main(d)
    space = '\n'
    f = re.findall(r'.*\n.*\n.*\n.*\n.*\n.*\n.*\n.*\n.*\n.*',space.join(y))
    if f[0].find('<吃掉了>')!=-1 or f[0].find('<全部吃掉了>')!=-1:
        return(f[0]+'\n...仅显示前5条内容\n检测到外来信息介入，请前往滥用日志查看所有消息。Special:滥用日志')
    else:
        return(f[0]+'\n...仅显示前5条内容')