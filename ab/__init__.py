# -*- coding:utf-8 -*-
import json
import requests

async def ab():
    url = 'https://minecraft-zh.gamepedia.com/api.php?action=query&list=abuselog&aflprop=user|title|action|result|filter&format=json'
    text1 = requests.get(url)
    file = json.loads(text1.text)
    return(file['query']['abuselog'][0]['title'] + ' - ' + file['query']['abuselog'][0]['user']+'\n处理结果：'+file['query']['abuselog'][0]['result'] +'\n'+file['query']['abuselog'][1]['title'] + ' - ' + file['query']['abuselog'][1]['user']+'\n处理结果：'+file['query']['abuselog'][1]['result'] +'\n'+file['query']['abuselog'][2]['title'] + ' - ' + file['query']['abuselog'][2]['user']+'\n处理结果：'+file['query']['abuselog'][2]['result'] +'\n'+file['query']['abuselog'][3]['title'] + ' - ' + file['query']['abuselog'][3]['user']+'\n处理结果：'+file['query']['abuselog'][3]['result'] +'\n'+file['query']['abuselog'][4]['title'] + ' - ' + file['query']['abuselog'][4]['user']+'\n处理结果：'+file['query']['abuselog'][4]['result'] +'…仅显示前5条内容。')