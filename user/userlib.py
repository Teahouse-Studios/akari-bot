import json
import re
import aiohttp
from UTC8 import UTC8
from .yhz import yhz
from .gender import gender
import re
import urllib

async def get_data(url: str, fmt: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(url,timeout=aiohttp.ClientTimeout(total=20)) as req:
            if hasattr(req, fmt):
                return await getattr(req, fmt)()
            else:
                raise ValueError(f"NoSuchMethod: {fmt}")

async def User1(url, str3):
    q = str3
    url1 = url+'api.php?action=query&list=users&ususers=' + q + '&usprop=groups%7Cblockinfo%7Cregistration%7Ceditcount%7Cgender&format=json'
    url2 = url+'api.php?action=query&meta=allmessages&ammessages=mainpage&format=json'
    file = await get_data(url1,'json')
    file2 = await get_data(url2,'json')
    try:
        Wikiname = file2['query']['allmessages'][0]['*']
    except Exception:
        Wikiname = 'Unknown'
    try:
        User = '用户：' + file['query']['users'][0]['name']
        Editcount = ' | 编辑数：' + str(file['query']['users'][0]['editcount'])
        Group = '用户组：' + yhz(str(file['query']['users'][0]['groups']))
        Gender = '性别：' + gender(file['query']['users'][0]['gender'])
        Registration = '注册时间：' + UTC8(file['query']['users'][0]['registration'],'full')
        Blockedby = str(file['query']['users'][0]['blockedby'])
        Blockedtimestamp = UTC8(file['query']['users'][0]['blockedtimestamp'],'full')
        Blockexpiry = UTC8(str(file['query']['users'][0]['blockexpiry']),'full')
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
            Registration = '注册时间：' + UTC8(file['query']['users'][0]['registration'],'full')
            g = re.sub('User:', '', str3)
            return(url+'UserProfile:' + urllib.parse.quote(g.encode('UTF-8')) + '\n'+Wikiname+'\n' + User + Editcount + '\n' + Group + '\n' + Gender + '\n' + Registration)
        except Exception:
            return('没有找到此用户。')