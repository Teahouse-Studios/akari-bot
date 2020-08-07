import json
import re
import requests
from .UTC8 import UTC8
from .yhz import yhz
from .gender import gender
from .UTC8V import UTC8V
import re
import urllib
def User1(url, str3):
    q = str3
    url1 = url+'api.php?action=query&list=users&ususers=' + q + '&usprop=groups%7Cblockinfo%7Cregistration%7Ceditcount%7Cgender&format=json'
    url2 = url+'api.php?action=query&meta=allmessages&ammessages=mainpage&format=json'
    s = requests.get(url1, timeout=10)
    file = json.loads(s.text)
    c = requests.get(url2, timeout=10)
    file2 = json.loads(c.text)
    try:
        Wikiname = file2['query']['allmessages'][0]['*']
    except Exception:
        Wikiname = 'Unknown'
    try:
        User = '用户：' + file['query']['users'][0]['name']
        Editcount = ' | 编辑数：' + str(file['query']['users'][0]['editcount'])
        Group = '用户组：' + yhz(str(file['query']['users'][0]['groups']))
        Gender = '性别：' + gender(file['query']['users'][0]['gender'])
        Registration = '注册时间：' + UTC8(file['query']['users'][0]['registration'])
        Blockedby = str(file['query']['users'][0]['blockedby'])
        Blockedtimestamp = UTC8(file['query']['users'][0]['blockedtimestamp'])
        Blockexpiry = UTC8V(str(file['query']['users'][0]['blockexpiry']))
        Blockreason = str(file['query']['users'][0]['blockreason'])
        try:
            g = re.sub('User:', '', str3)
            if not Blockreason:
                return(url+'UserProfile:' + urllib.parse.quote(g.encode('UTF-8')) + '\n'+Wikiname+'\n' + User + Editcount + '\n' + Group + '\n' + Gender + '\n' + Registration + '\n' +file['query']['users'][0]['name'] + '正在被封禁！\n被' + Blockedby + '封禁，时间从' + Blockedtimestamp + '到' + Blockexpiry)
            else:
                return(url+'UserProfile:' + urllib.parse.quote(g.encode('UTF-8')) + '\n'+Wikiname+'\n' + User + '\n' + Editcount + '\n' + Group + '\n' + Gender + '\n' + Registration + '\n' +file['query']['users'][0]['name'] + '正在被封禁！\n被' + Blockedby + '封禁，时间从' + Blockedtimestamp + '到' + Blockexpiry + '，理由：“' + Blockreason + '”')
        except Exception:
            g = re.sub('User:', '', str3)
            if not Blockreason:
                return(url+'UserProfile:' + urllib.parse.quote(g.encode('UTF-8')) + '\n'+Wikiname+'\n' + User + Editcount + '\n' + Group + '\n' + Gender + '\n' + Registration + '\n' +file['query']['users'][0]['name'] + '正在被封禁！\n被' + Blockedby + '封禁，时间从' + Blockedtimestamp + '到' + Blockexpiry)
            else:
                return(url+'UserProfile:' + urllib.parse.quote(str3.encode('UTF-8')) + '\n'+Wikiname+'\n' + User + Editcount + '\n' + Group + '\n' + Gender + '\n' + Registration + '\n' +file['query']['users'][0]['name'] + '正在被封禁！\n被' + Blockedby + '封禁，时间从' + Blockedtimestamp + '到' + Blockexpiry + '，理由：“' + Blockreason + '”')
    except Exception:
        try:
            User = '用户：' + file['query']['users'][0]['name']
            Editcount = ' | 编辑数：' + str(file['query']['users'][0]['editcount'])
            Group = '用户组：' + yhz(str(file['query']['users'][0]['groups']))
            Gender = '性别：' + gender(file['query']['users'][0]['gender'])
            Registration = '注册时间：' + UTC8(file['query']['users'][0]['registration'])
            g = re.sub('User:', '', str3)
            return(url+'UserProfile:' + urllib.parse.quote(g.encode('UTF-8')) + '\n'+Wikiname+'\n' + User + Editcount + '\n' + Group + '\n' + Gender + '\n' + Registration)
        except Exception:
            return('没有找到此用户。')