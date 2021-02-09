import re
import urllib

import aiohttp

from modules.utils.UTC8 import UTC8
from .tool import gender
from modules.wiki.wikilib import wikilib
from modules.wiki.helper import check_wiki_available


async def get_data(url: str, fmt: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as req:
            if hasattr(req, fmt):
                return await getattr(req, fmt)()
            else:
                raise ValueError(f"NoSuchMethod: {fmt}")


async def getwikiname(wikiurl):
    try:
        wikinameurl = wikiurl + '?action=query&meta=allmessages&ammessages=mainpage&format=json'
        wikiname = await get_data(wikinameurl, 'json')
        Wikiname = wikiname['query']['allmessages'][0]['*']
    except Exception:
        Wikiname = 'Unknown'
    return Wikiname


async def get_user_group(wikiurl):
    groups = {}
    user_group_link = wikiurl + '?action=query&meta=allmessages&amprefix=group-&format=json'
    get_json = await get_data(user_group_link, 'json')
    j = get_json['query']['allmessages']
    for x in j:
        groups[x['name']] = x['*']
    return groups


def trans_user_group(user_group: list, group_dict: dict):
    trans = []
    for x in user_group:
        if x in group_dict:
            trans.append(group_dict[x])
        else:
            trans.append(x)
    return '、'.join(trans)


def d(str1):
    a = re.sub(r'<dd>|</dd>', '', str1)
    return a


async def GetUser(wikiurl, username, argv=None):
    GetInterwiki = await wikilib().get_interwiki(wikiurl)
    match_interwiki = re.match(r'(.*?):(.*)', username)
    if match_interwiki:
        if match_interwiki.group(1) in GetInterwiki:
            wikiurl = await check_wiki_available(GetInterwiki[match_interwiki.group(1)])
            if wikiurl:
                return await GetUser(wikiurl, match_interwiki.group(2), argv)
    UserJsonURL = wikiurl + '?action=query&list=users&ususers=' + username + '&usprop=groups%7Cblockinfo%7Cregistration%7Ceditcount%7Cgender&format=json'
    GetUserJson = await get_data(UserJsonURL, 'json')
    Wikiname = await getwikiname(wikiurl)
    GetUserGroupsList = await get_user_group(wikiurl)
    try:
        User = GetUserJson['query']['users'][0]['name']
        Editcount = str(GetUserJson['query']['users'][0]['editcount'])
        Group = trans_user_group(GetUserJson['query']['users'][0]['groups'], GetUserGroupsList)
        Gender = gender(GetUserJson['query']['users'][0]['gender'])
        Registration = UTC8(GetUserJson['query']['users'][0]['registration'], 'full')
        rmuser = re.sub('User:', '', username)
        Blockmessage = ''
        if 'blockedby' in GetUserJson['query']['users'][0]:
            BlockedBy = GetUserJson['query']['users'][0]['blockedby']
            if BlockedBy:
                Blockedtimestamp = UTC8(GetUserJson['query']['users'][0]['blockedtimestamp'], 'full')
                Blockexpiry = UTC8(str(GetUserJson['query']['users'][0]['blockexpiry']), 'full')
                Blockmessage = f'\n{User}正在被封禁！' + \
                               f'\n被{BlockedBy}封禁，时间从{Blockedtimestamp}到{Blockexpiry}'
                if 'blockreason' in GetUserJson['query']['users'][0]:
                    Blockreason = GetUserJson['query']['users'][0]['blockreason']
                    if Blockreason:
                        Blockmessage += f'，理由：“{Blockreason}”'
        if argv == '-r' or argv == '-p':
            from bs4 import BeautifulSoup as bs
            wikiurl = re.sub('api.php', '', wikiurl)
            clawerurl = wikiurl + 'UserProfile:' + username
            clawer = await get_data(clawerurl, 'text')
            soup = bs(clawer, 'html.parser')
            stats = soup.find('div', class_='section stats')
            point = soup.find('div', class_='score').text
            dd = stats.find_all('dd')
            Editcount = ('\n编辑过的Wiki：' + str(dd[0]) + '\n创建数：' + str(dd[1]) + ' | 编辑数：' + str(dd[2]) + '\n删除数：' + str(
                dd[3]) + ' | 巡查数：' + str(dd[4]) + '\n本站排名：' + str(dd[5]) + ' | 全域排名：' + str(dd[6]) + '\n好友：' + str(
                dd[7]))
            Editcount = re.sub(r'<dd>|</dd>', '', Editcount)
            Editcount += f' | Wikipoints：{point}'
            if argv == '-p':
                import uuid
                import os
                Registration = UTC8(GetUserJson['query']['users'][0]['registration'], 'notimezone')

                matchlink = re.match(r'https?://(.*)/', wikiurl)
                filepath = os.path.abspath('./assets/Favicon/' + matchlink.group(1) + '/')
                if not os.path.exists(filepath):
                    favicon_path = os.path.abspath('./assets/Favicon/')
                    if not os.path.exists(favicon_path):
                        os.mkdir(favicon_path)
                    os.mkdir(filepath)
                wikipng = os.path.abspath('./assets/Favicon/' + matchlink.group(1) + '/Wiki.png')
                if not os.path.exists(wikipng):
                    from .dpng import dpng
                    if not dpng(wikiurl, matchlink.group(1)):
                        raise
                from .tpg import tpg
                try:
                    BlockedBy = GetUserJson['query']['users'][0]['blockedby']
                    if BlockedBy:
                        Blockedtimestamp = UTC8(GetUserJson['query']['users'][0]['blockedtimestamp'], 'notimezone')
                        Blockexpiry = UTC8(str(GetUserJson['query']['users'][0]['blockexpiry']), 'notimezone')
                        Brs = 1
                        try:
                            from .hh import hh1
                            Blockreason = hh1(GetUserJson['query']['users'][0]['blockreason'])
                            Brs = 2
                        except KeyError:
                            pass
                        if Brs == 1:
                            imagepath = tpg(favicon=wikipng,
                                            wikiname=Wikiname,
                                            username=User,
                                            gender=Gender,
                                            registertime=Registration,
                                            contributionwikis=d(str(dd[0])),
                                            createcount=d(str(dd[1])),
                                            editcount=d(str(dd[2])),
                                            deletecount=d(str(dd[3])),
                                            patrolcount=d(str(dd[4])),
                                            sitetop=d(str(dd[5])),
                                            globaltop=d(str(dd[6])),
                                            wikipoint=point,
                                            blockbyuser=BlockedBy,
                                            blocktimestamp1=Blockedtimestamp,
                                            blocktimestamp2=Blockexpiry,
                                            bantype='YN')
                        elif Brs == 2:
                            imagepath = tpg(favicon=wikipng,
                                            wikiname=Wikiname,
                                            username=User,
                                            gender=Gender,
                                            registertime=Registration,
                                            contributionwikis=d(str(dd[0])),
                                            createcount=d(str(dd[1])),
                                            editcount=d(str(dd[2])),
                                            deletecount=d(str(dd[3])),
                                            patrolcount=d(str(dd[4])),
                                            sitetop=d(str(dd[5])),
                                            globaltop=d(str(dd[6])),
                                            wikipoint=point,
                                            blockbyuser=BlockedBy,
                                            blocktimestamp1=Blockedtimestamp,
                                            blocktimestamp2=Blockexpiry,
                                            blockreason=Blockreason,
                                            bantype='Y')
                except KeyError:
                    imagepath = tpg(favicon=wikipng,
                                    wikiname=Wikiname,
                                    username=User,
                                    gender=Gender,
                                    registertime=Registration,
                                    contributionwikis=d(str(dd[0])),
                                    createcount=d(str(dd[1])),
                                    editcount=d(str(dd[2])),
                                    deletecount=d(str(dd[3])),
                                    patrolcount=d(str(dd[4])),
                                    sitetop=d(str(dd[5])),
                                    globaltop=d(str(dd[6])),
                                    wikipoint=point)
        if argv == '-p':
            return f'{wikiurl}UserProfile:{urllib.parse.quote(rmuser.encode("UTF-8"))}[[uimgc:{imagepath}]]'
        return (wikiurl + 'UserProfile:' + urllib.parse.quote(rmuser.encode('UTF-8')) + '\n' +
                Wikiname + '\n' +
                f'用户：{User} | 编辑数：{Editcount}\n' +
                f'用户组：{Group}\n' +
                f'性别：{Gender}\n' +
                f'注册时间：{Registration}' + Blockmessage)
    except Exception as e:
        if 'missing' in GetUserJson['query']['users'][0]:
            return '没有找到此用户。'
        else:
            return '发生错误：' + e
            import traceback
            traceback.print_exc()
