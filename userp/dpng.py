from bs4 import BeautifulSoup as bs
import requests
import re
import os
def dpng(link,ss):
    q = requests.get(link+'/File:Wiki.png',timeout=10)
    soup = bs(q.text,'html.parser')
    aa = soup.find('div',id='mw-content-text')
    src = aa.find_all('div',class_='fullImageLink')
    z = re.match('.*<a href="(.*)"><.*',str(src),re.S)
    url  =z.group(1)
    d='/home/wdljt/oasisakari/bot/assests/Favicon/'+ss+'/'
    if not os.path.exists(d):
        os.makedirs(d)
    path=d+'Wiki.png'

    try:
        if not os.path.exists(d):
            os.mkdir(d)
        if not os.path.exists(path):
            r=requests.get(url,timeout=30)
            r.raise_for_status()
            with open(path,'wb') as f:
                f.write(r.content)
                f.close()
                print("图片保存成功")
        else:
            print("图片已存在")
    except Exception as e:
        print(str(e))