import aiohttp
import json
import re
import traceback
import urllib

from modules.UTC8 import UTC8
from .gender import gender
from .puserlib import PUser1
from modules import checkuser

async def userpic(message):
    c = message
    f = re.sub(' -p', '', c)
    print(f)
    z = re.sub(r'^User', 'user', f)
    g = re.match(r'^user ~(.*) (.*)', z)
    if g:
        h = g.group(1)
        h2 = g.group(2)
        h2 = re.sub('_', ' ', h2)
    g = re.match(r'^user-(.*?) (.*)', z)
    if g:
        h = 'minecraft-' + g.group(1)
        h2 = g.group(2)
        h2 = re.sub('_', ' ', h2)
    g = re.match(r'^user (.*?):(.*)', z)
    if g:
        h = 'minecraft-' + g.group(1)
        h2 = g.group(2)
        h2 = re.sub('_', ' ', h2)
    g = re.match(r'user (.*)', z)
    if g:
        h = 'minecraft'
        h2 = g.group(1)
        h2 = re.sub('_', ' ', h2)
    if checkuser(h, h2):
        h2 = re.sub('User:', '', h2)
        print(h2)
        return await Userp(h, h2) + "[[usn:" + h2 + "]]"
    else:
        return '没有找到此用户。'

async def Userp(path, Username):
    try:
        q = re.sub('User:', '', Username)
        q = re.sub('_', ' ', q)
        metaurl = 'https://' + path + '.gamepedia.com'
        url1 = metaurl + '/api.php?action=query&list=users&ususers=' + q + '&usprop=groups%7Cblockinfo%7Cregistration%7Ceditcount%7Cgender&format=json'
        async with aiohttp.ClientSession() as session:
            async with session.get(url1, timeout=aiohttp.ClientTimeout(total=20)) as req:
                if req.status != 200:
                    print(f"请求时发生错误：{req.status}")
                else:
                    s = await req.text()
        file = json.loads(s)
        try:
            User = file['query']['users'][0]['name']
            Gender = gender(file['query']['users'][0]['gender'])
            Registration = UTC8(file['query']['users'][0]['registration'], 'notimezone')
            Blockedby = str(file['query']['users'][0]['blockedby'])
            Blockedtimestamp = UTC8(file['query']['users'][0]['blockedtimestamp'], 'notimezone')
            Blockexpiry = UTC8(str(file['query']['users'][0]['blockexpiry']), 'full')
            Blockreason = str(file['query']['users'][0]['blockreason'])
            if not Blockreason:
                await PUser1(metaurl, q, path, User, Gender, Registration, Blockedby, Blockedtimestamp, Blockexpiry)
            else:
                await PUser1(metaurl, q, path, User, Gender, Registration, Blockedby, Blockedtimestamp, Blockexpiry, \
                                Blockreason)
            h = '/Userprofile:' + User
            return (metaurl + urllib.parse.quote(h.encode('UTF-8')))
        except Exception:
            try:
                User = file['query']['users'][0]['name']
                Gender = gender(file['query']['users'][0]['gender'])
                Registration = UTC8(file['query']['users'][0]['registration'], 'notimezone')
                await PUser1(metaurl, q, path, User, Gender, Registration)
                h = '/Userprofile:' + User
                return (metaurl + urllib.parse.quote(h.encode('UTF-8')))
            except Exception:
                traceback.print_exc()
                return ('N')
    except Exception as e:
        return ('发生错误：' + str(e))
