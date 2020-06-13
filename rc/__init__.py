# -*- coding:utf-8 -*-
import json
import requests
async def rc():
    url = 'https://minecraft-zh.gamepedia.com/api.php?action=query&list=recentchanges&rcprop=title|user|timestamp&rctype=edit|new&format=json'
    text1 = requests.get(url,timeout=10)
    file = json.loads(text1.text)
    return (file['query']['recentchanges'][0]['title'] + ' - ' + file['query']['recentchanges'][0]['user'] +' '+file['query']['recentchanges'][0]['timestamp'] +'\n'+file['query']['recentchanges'][1]['title'] + ' - ' + file['query']['recentchanges'][1]['user'] +' '+file['query']['recentchanges'][1]['timestamp']+'\n'+file['query']['recentchanges'][2]['title'] + ' - ' + file['query']['recentchanges'][2]['user'] +' '+file['query']['recentchanges'][2]['timestamp']+'\n'+file['query']['recentchanges'][3]['title'] + ' - ' + file['query']['recentchanges'][3]['user'] +' '+file['query']['recentchanges'][3]['timestamp']+'\n'+file['query']['recentchanges'][4]['title'] + ' - ' + file['query']['recentchanges'][4]['user'] +' '+file['query']['recentchanges'][4]['timestamp']+'\n'+file['query']['recentchanges'][5]['title'] + ' - ' + file['query']['recentchanges'][5]['user'] +' '+file['query']['recentchanges'][5]['timestamp']+'\n'+'…仅显示前5条内容。')