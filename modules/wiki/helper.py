import re
import traceback

import aiohttp
import json


async def get_url(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as req:
            return json.loads(await req.read())


async def check_wiki_available(link):
    query = '?action=query&meta=siteinfo&siprop=general|extensions&format=json'
    try:
        api = re.match(r'(https?://.*?/api.php$)', link)
        wlink = api.group(1)
        json1 = await get_url(api.group(1) + query)
    except:
        if link[-1] not in ['/', '\\']:
            link = link + '/'
        test1 = link + 'api.php' + query
        try:
            json1 = await get_url(test1)
            wlink = link + 'api.php' + query
        except:
            try:
                test2 = link + 'w/' + query
                json1 = await get_url(test2)
                wlink = link + 'w/api.php' + query
            except:
                traceback.print_exc()
                return False
    wikiname = json1['query']['general']['sitename']
    extensions = json1['query']['extensions']
    extlist = []
    for ext in extensions:
        extlist.append(ext['name'])
    print(extlist)
    if 'TextExtracts' not in extlist:
        wikiname = wikiname + '\n警告：此wiki没有启用TextExtracts扩展，返回的页面预览内容将为未处理的原始Wikitext文本。'

    return wlink, wikiname
