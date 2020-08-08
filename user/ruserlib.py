import json
import re
import requests
from UTC8 import UTC8
from .yhz import yhz
from .gender import gender
import re
import urllib
from bs4 import BeautifulSoup as bs
def rUser1(url, str3):
    q = str3
    url1 = url+'api.php?action=query&list=users&ususers=' + q + '&usprop=groups%7Cblockinfo%7Cregistration%7Ceditcount%7Cgender&format=json'
    url2 = url+'api.php?action=query&meta=allmessages&ammessages=mainpage&format=json'
    s = requests.get(url1, timeout=10)
    file = json.loads(s.text)
    c = requests.get(url2, timeout=10)
    file2 = json.loads(c.text)
    url3 = url + 'UserProfile:' + q
    res = requests.get(url3, timeout=10)
    try:
        Wikiname = file2['query']['allmessages'][0]['*']
    except Exception:
        Wikiname = 'Unknown'
    try:
        User = '用户：' + file['query']['users'][0]['name']
        Group = '用户组：' + yhz(str(file['query']['users'][0]['groups']))
        Gender = '性别：' + gender(file['query']['users'][0]['gender'])
        Registration = '注册时间：' + UTC8(file['query']['users'][0]['registration'],'full')
        Blockedby = str(file['query']['users'][0]['blockedby'])
        Blockedtimestamp = UTC8(file['query']['users'][0]['blockedtimestamp'],'full')
        Blockexpiry = UTC8(str(file['query']['users'][0]['blockexpiry']),'full')
        Blockreason = str(file['query']['users'][0]['blockreason'])
        soup = bs(res.text, 'html.parser')
        stats = soup.find('div', class_='section stats')
        point = soup.find('div', class_='score').text
        dd = stats.find_all('dd')
        a = ('\n编辑过的Wiki：' + str(dd[0]) + '\n创建数：' + str(dd[1]) + ' | 编辑数：' + str(dd[2]) + '\n删除数：' + str(dd[3]) + ' | 巡查数：' + str(dd[4]) + '\n本站排名：' + str(dd[5]) + ' | 全域排名：' + str(dd[6]) + '\n好友：' + str(dd[7]))
        a = re.sub('<dd>', '', a)
        a = re.sub('</dd>', '', a)
        g = re.sub('User:', '', str3)
        if not Blockreason:
            return(url+'UserProfile:' + urllib.parse.quote(g.encode('UTF-8')) + '\n'+Wikiname+'\n' + User + a +' | WikiPoints：'+ point + '\n' + Group + '\n' + Gender + '\n' + Registration + '\n' +file['query']['users'][0]['name'] + '正在被封禁！\n被' + Blockedby + '封禁，时间从' + Blockedtimestamp + '到' + Blockexpiry)
        else:
            return(url+'UserProfile:' + urllib.parse.quote(g.encode('UTF-8')) + '\n'+Wikiname+'\n' + User + a + ' | WikiPoints：'+ point + '\n' + '\n' + Group + '\n' + Gender + '\n' + Registration + '\n' +file['query']['users'][0]['name'] + '正在被封禁！\n被' + Blockedby + '封禁，时间从' + Blockedtimestamp + '到' + Blockexpiry + '，理由：“' + Blockreason + '”')
    except Exception:
        try:
            User = '用户：' + file['query']['users'][0]['name']
            Group = '用户组：' + yhz(str(file['query']['users'][0]['groups']))
            Gender = '性别：' + gender(file['query']['users'][0]['gender'])
            Registration = '注册时间：' + UTC8(file['query']['users'][0]['registration'],'full')
            soup = bs(res.text, 'html.parser')
            stats = soup.find('div', class_='section stats')
            point = soup.find('div', class_='score').text
            dd = stats.find_all('dd')
            a = ('\n编辑过的Wiki：' + str(dd[0]) + '\n创建数：' + str(dd[1]) + ' | 编辑数：' + str(dd[2]) + '\n删除数：' + str(dd[3]) + ' | 巡查数：' + str(dd[4]) + '\n本站排名：' + str(dd[5]) + ' | 全域排名：' + str(dd[6]) + '\n好友：' + str(dd[7]))
            a = re.sub('<dd>', '', a)
            a = re.sub('</dd>', '', a)
            g = re.sub('User:', '', str3)
            return(url+'UserProfile:' + urllib.parse.quote(g.encode('UTF-8')) + '\n'+Wikiname+'\n' + User +a + ' | WikiPoints：'+ point + '\n' + Group + '\n' + Gender + '\n' + Registration)
        except Exception:
            return('没有找到此用户。'+str3)