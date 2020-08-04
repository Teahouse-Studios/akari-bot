import json
import re
import requests
import re
from bs4 import BeautifulSoup as bs
import os
from .killdd import ddk
from .hh import hh
from .hh17 import hh17
from os.path import abspath
def PUser1(url, str3,ss,User,Gender,Registration):
    q = str3
    url2 = url+'/api.php?action=query&meta=allmessages&ammessages=mainpage&format=json'
    c = requests.get(url2, timeout=10)
    file2 = json.loads(c.text)
    try:
        Wikiname = file2['query']['allmessages'][0]['*']
    except Exception:
        Wikiname = 'Unknown'
    d= abspath('./assests/Favicon/'+ss+'/')
    if not os.path.exists(d):
        os.mkdir(d)
    ddd = abspath('./assests/Favicon/'+ss+'/Wiki.png')
    if not os.path.exists(ddd):
        from .dpng import dpng
        dpng(url,ss)
    try:
        url2 = url+'/UserProfile:'+q
        res = requests.get(url2)
        soup = bs(res.text, 'html.parser')
        stats = soup.find('div', class_='section stats')
        point = soup.find('div', class_='score').text
        dd = stats.find_all('dd')
        for tag in dd:
            pass
        g = re.sub('User:', '', str3)
        from .tpg import tpg
        tpg(abspath('./assests/Favicon/'+ss+'/Wiki.png'),hh(Wikiname),User,Gender,Registration,ddk(str(dd[0])),ddk(str(dd[1])),ddk(str(dd[2])),ddk(str(dd[3])),ddk(str(dd[4])),ddk(str(dd[5])),ddk(str(dd[6])),point)
    except Exception:
        return False
def PUser1ban(url, str3,ss,User,Gender,Registration,Blockedby,Blockedtimestamp,Blockexpiry,Blockreason):
    q = str3
    url2 = url+'/api.php?action=query&meta=allmessages&ammessages=mainpage&format=json'
    c = requests.get(url2, timeout=10)
    file2 = json.loads(c.text)
    try:
        Wikiname = file2['query']['allmessages'][0]['*']
    except Exception:
        Wikiname = 'Unknown'
    d=abspath('./assests/Favicon/'+ss+'/')
    if not os.path.exists(d):
        os.mkdir(d)
    ddd=abspath('./assests/Favicon/'+ss+'/Wiki.png')
    if not os.path.exists(ddd):
        from .dpng import dpng
        dpng(url,ss)
    try:
        url2 = url+'/UserProfile:'+q
        res = requests.get(url2)
        soup = bs(res.text, 'html.parser')
        stats = soup.find('div', class_='section stats')
        point = soup.find('div', class_='score').text
        dd = stats.find_all('dd')
        for tag in dd:
            pass
        g = re.sub('User:', '', str3)
        from .tpgban import tpgban
        tpgban(abspath('./assests/Favicon/'+ss+'/Wiki.png'),hh(Wikiname),User,Gender,Registration,ddk(str(dd[0])),ddk(str(dd[1])),ddk(str(dd[2])),ddk(str(dd[3])),ddk(str(dd[4])),ddk(str(dd[5])),ddk(str(dd[6])),point,Blockedby,Blockedtimestamp,Blockexpiry,hh17(Blockreason))
    except Exception:
        return False
def PUser1bann(url, str3,ss,User,Gender,Registration,Blockedby,Blockedtimestamp,Blockexpiry):
    q = str3
    url2 = url+'/api.php?action=query&meta=allmessages&ammessages=mainpage&format=json'
    c = requests.get(url2, timeout=10)
    file2 = json.loads(c.text)
    try:
        Wikiname = file2['query']['allmessages'][0]['*']
    except Exception:
        Wikiname = 'Unknown'
    d=abspath('./assests/Favicon/'+ss+'/')
    if not os.path.exists(d):
        os.mkdir(d)
    ddd = abspath('./assests/Favicon/'+ss+'/Wiki.png')
    if not os.path.exists(ddd):
        from .dpng import dpng
        dpng(url,ss)
    try:
        url2 = url+'/UserProfile:'+q
        res = requests.get(url2)
        soup = bs(res.text, 'html.parser')
        stats = soup.find('div', class_='section stats')
        point = soup.find('div', class_='score').text
        dd = stats.find_all('dd')
        for tag in dd:
            pass
        g = re.sub('User:', '', str3)
        from .tpgbann import tpgbann
        tpgbann(abspath('./assests/Favicon/'+ss+'/Wiki.png'),hh(Wikiname),User,Gender,Registration,ddk(str(dd[0])),ddk(str(dd[1])),ddk(str(dd[2])),ddk(str(dd[3])),ddk(str(dd[4])),ddk(str(dd[5])),ddk(str(dd[6])),point,Blockedby,Blockedtimestamp,Blockexpiry)
    except Exception:
        return False