import os
from os.path import abspath

import aiohttp

from modules.wiki.wikilib_v2 import WikiLib


async def dpng(link, ss):
    check = await WikiLib(link).check_wiki_available()
    if check:
        imgurl = check.value.logo_url
        if imgurl is not None:
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
    return False
