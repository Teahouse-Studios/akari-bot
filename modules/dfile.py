import os
import re
import uuid
from os.path import abspath

import aiohttp
from bs4 import BeautifulSoup as bs


async def dfile(link, filename):
    suffix = re.match(r'.*(\..*)$', filename)
    async with aiohttp.ClientSession() as session:
        async with session.get(link + 'File:' + filename) as req:
            if req.status != 200:
                return f"请求时发生错误：{req.status}"
            else:
                q = await req.text()
    soup = bs(q, 'html.parser')
    aa = soup.find('div', id='mw-content-text')
    aaa = aa.find('div', class_='fullImageLink', id='file')
    aaaa = aaa.find('audio')
    print(aaaa)
    z = re.match('.*<.*src="(.*)".*><.*', str(aaa), re.S)
    url = z.group(1)
    print(url)
    d = abspath('./assets/cache/')
    if not os.path.exists(d):
        os.makedirs(d)
    print(suffix.group(1))
    path = d + '/' + str(uuid.uuid4()) + suffix.group(1)
    print(path)
    try:
        if not os.path.exists(d):
            os.mkdir(d)
        if not os.path.exists(path):
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as r:
                    with open(path, "wb") as fp:
                        chunk = await r.content.read()
                        fp.write(chunk)
            return path
        else:
            print("已存在")
            return path
    except Exception as e:
        print(str(e))
