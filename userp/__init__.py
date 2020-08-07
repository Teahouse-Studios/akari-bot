from .puserlib import PUser1, PUser1ban, PUser1bann
import requests
import json
import re
from .UTC8U import UTC8U
from .gender import gender
from .UTC8V import UTC8V
import urllib

async def Userp(path,Username):
    try:
        q = re.sub('User:', '', Username)
        q = re.sub('_', ' ', q)
        metaurl = 'https://' + path + '.gamepedia.com'
        url1 = metaurl + '/api.php?action=query&list=users&ususers=' + q + '&usprop=groups%7Cblockinfo%7Cregistration%7Ceditcount%7Cgender&format=json'
        s = requests.get(url1, timeout=10)
        file = json.loads(s.text)
        try:
            User = file['query']['users'][0]['name']
            Gender = gender(file['query']['users'][0]['gender'])
            Registration = UTC8U(file['query']['users'][0]['registration'])
            Blockedby = str(file['query']['users'][0]['blockedby'])
            Blockedtimestamp = UTC8U(file['query']['users'][0]['blockedtimestamp'])
            Blockexpiry = UTC8V(str(file['query']['users'][0]['blockexpiry']))
            Blockreason = str(file['query']['users'][0]['blockreason'])
            if not Blockreason:
                PUser1bann(metaurl, q, path, User, Gender, Registration, Blockedby, Blockedtimestamp, Blockexpiry)
            else:
                PUser1ban(metaurl, q, path, User, Gender, Registration, Blockedby, Blockedtimestamp, Blockexpiry,
                          Blockreason)
            h = '/Userprofile:' +User
            return(metaurl+urllib.parse.quote(h.encode('UTF-8')))
        except Exception:
            try:
                User = file['query']['users'][0]['name']
                Gender = gender(file['query']['users'][0]['gender'])
                Registration = UTC8U(file['query']['users'][0]['registration'])
                PUser1(metaurl, q, path, User, Gender, Registration)
                h = '/Userprofile:' +User
                return(metaurl+urllib.parse.quote(h.encode('UTF-8')))
            except Exception:
                return ('N')
    except Exception as e:
        return ('发生错误：'+str(e))