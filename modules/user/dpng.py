import os
import re
from os.path import abspath

import aiohttp

from modules.wiki.wikilib import wikilib


async def dpng(link, ss):
    link = await wikilib().get_article_path(link)
    imgurl = await wikilib().get_image('File:Wiki.png', link)
    d = abspath('./assets/Favicon/' + ss + '/')
    if not os.path.exists(d):
        os.makedirs(d)
    path = d + '/Wiki.png'

    try:
        if not os.path.exists(d):
            os.mkdir(d)
        if not os.path.exists(path):
            async with aiohttp.ClientSession() as session:
                async with session.get(imgurl) as resp:
                    with open(path, 'wb+') as jpg:
                        jpg.write(await resp.read())
                        return True
        else:
            return True
    except Exception:
        return False
