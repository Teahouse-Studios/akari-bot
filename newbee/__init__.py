# -*- coding:utf-8 -*-
import json 
import requests

async def newnew():
    try:
        url = 'https://minecraft-zh.gamepedia.com/api.php?action=query&list=logevents&letype=newusers&format=json'
        text1 = requests.get(url,timeout=10)
        file = json.loads(text1.text)
        return('这是当前的新人列表：\n'+file['query']['logevents'][0]['title'] + '\n'+file['query']['logevents'][1]['title']+'\n'+file['query']['logevents'][2]['title'] +'\n'+file['query']['logevents'][3]['title']+'\n'+file['query']['logevents'][4]['title'] + '\n'+'…仅显示前5条内容。')
    except Exception as e:
        return('发生错误：'+str(e))