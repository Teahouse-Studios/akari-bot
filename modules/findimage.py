import re

import aiohttp
from bs4 import BeautifulSoup as bs


async def findimage(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as req:
            if req.status != 200:
                return f"请求时发生错误：{req.status}"
            else:
                q = await req.text()
    soup = bs(q, 'html.parser')
    aa = soup.find('div', id='mw-content-text')
    src = aa.find_all('div', class_='fullImageLink')
    z = re.match('.*<a href="(.*)"><.*', str(src), re.S)
    find = re.sub(r'\?.*', '', z.group(1))
    return find
