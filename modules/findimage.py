import re

import traceback

import aiohttp
from bs4 import BeautifulSoup as bs


async def findimage(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as req:
            if req.status != 200:
                return None
            else:
                q = await req.text()
    try:
        soup = bs(q, 'html.parser')
        aa = soup.find('div', id='mw-content-text')
        src = aa.find_all('div', class_='fullImageLink')
        z = re.match('.*<a href="(.*)"><.*', str(src), re.S)
        find = re.sub(r'\?.*', '', z.group(1))
        return find
    except Exception:
        traceback.print_exc()
        return None
