import re

import aiohttp


async def get_url(url, fmt):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as req:
            if hasattr(req, fmt):
                return await getattr(req, fmt)()
            else:
                raise ValueError(f"NoSuchMethod: {fmt}")


async def check_wiki_available(link):
    try:
        api = re.match(r'(https?://.*?/api.php$)', link)
        json1 = await get_url(api.group(1), 'json')
        wikiname = json1['query']['general']['sitename']
        return api.group(1), wikiname
    except:
        pass
    if link[-1] not in ['/', '\\']:
        link = link + '/'
    test1 = link + 'api.php?action=query&meta=siteinfo&format=json'
    try:
        json1 = await get_url(test1, 'json')
        wikiname = json1['query']['general']['sitename']
        return link + 'api.php', wikiname
    except:
        pass
    try:
        test2 = link + 'w/api.php?action=query&meta=siteinfo&format=json'
        json2 = await get_url(test2, 'json')
        wikiname = json2['query']['general']['sitename']
        return link + 'w/api.php', wikiname
    except:
        return False
