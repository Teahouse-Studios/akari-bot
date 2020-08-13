import aiohttp
import re
import urllib
from bs4 import BeautifulSoup as bs

from UTC8 import UTC8
from .gender import gender
from .yhz import yhz


async def get_data(url: str, fmt: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as req:
            if hasattr(req, fmt):
                return await getattr(req, fmt)()
            else:
                raise ValueError(f"NoSuchMethod: {fmt}")


async def rUser1(url, username):
    descurl = url + 'api.php?action=query&list=users&ususers=' + username + '&usprop=groups%7Cblockinfo%7Cregistration%7Ceditcount%7Cgender&format=json'
    wikinameurl = url + 'api.php?action=query&meta=allmessages&ammessages=mainpage&format=json'
    desc = await get_data(descurl, 'json')
    wikiname = await get_data(wikinameurl, 'json')
    clawerurl = url + 'UserProfile:' + username
    clawer = await get_data(clawerurl, 'text')
    try:
        Wikiname = wikiname['query']['allmessages'][0]['*']
    except Exception:
        Wikiname = 'Unknown'
    try:
        User = '用户：' + desc['query']['users'][0]['name']
        Group = '用户组：' + yhz(str(desc['query']['users'][0]['groups']))
        Gender = '性别：' + gender(desc['query']['users'][0]['gender'])
        Registration = '注册时间：' + UTC8(desc['query']['users'][0]['registration'], 'full')
        soup = bs(clawer, 'html.parser')
        stats = soup.find('div', class_='section stats')
        point = soup.find('div', class_='score').text
        dd = stats.find_all('dd')
        a = ('\n编辑过的Wiki：' + str(dd[0]) + '\n创建数：' + str(dd[1]) + ' | 编辑数：' + str(dd[2]) + '\n删除数：' + str(
            dd[3]) + ' | 巡查数：' + str(dd[4]) + '\n本站排名：' + str(dd[5]) + ' | 全域排名：' + str(dd[6]) + '\n好友：' + str(dd[7]))
        a = re.sub('<dd>', '', a)
        a = re.sub('</dd>', '', a)
        g = re.sub('User:', '', username)
        try:
            Blockedby = str(desc['query']['users'][0]['blockedby'])
            Blockedtimestamp = UTC8(desc['query']['users'][0]['blockedtimestamp'], 'full')
            Blockexpiry = UTC8(str(desc['query']['users'][0]['blockexpiry']), 'full')
            Blockreason = str(desc['query']['users'][0]['blockreason'])
            if not Blockreason:
                return (url + 'UserProfile:' + urllib.parse.quote(g.encode(
                    'UTF-8')) + '\n' + Wikiname + '\n' + User + a + ' | WikiPoints：' + point + '\n' + Group + '\n' + Gender + '\n' + Registration + '\n' +
                        desc['query']['users'][0][
                            'name'] + '正在被封禁！\n被' + Blockedby + '封禁，时间从' + Blockedtimestamp + '到' + Blockexpiry)
            else:
                return (url + 'UserProfile:' + urllib.parse.quote(g.encode(
                    'UTF-8')) + '\n' + Wikiname + '\n' + User + a + ' | WikiPoints：' + point + '\n' + '\n' + Group + '\n' + Gender + '\n' + Registration + '\n' +
                        desc['query']['users'][0][
                            'name'] + '正在被封禁！\n被' + Blockedby + '封禁，时间从' + Blockedtimestamp + '到' + Blockexpiry + '，理由：“' + Blockreason + '”')
        except Exception:
            return (url + 'UserProfile:' + urllib.parse.quote(g.encode(
                'UTF-8')) + '\n' + Wikiname + '\n' + User + a + ' | WikiPoints：' + point + '\n' + Group + '\n' + Gender + '\n' + Registration)
    except Exception:
        return ('没有找到此用户。' + username)