import datetime
import json
import re
import traceback

import aiohttp

from .database import WikiDB


async def get_data(url: str, fmt: str, headers=None):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as req:
                if hasattr(req, fmt):
                    return await getattr(req, fmt)()
                else:
                    raise ValueError(f"NoSuchMethod: {fmt}")
        except Exception:
            traceback.print_exc()
            return False


async def check_wiki_available(link):
    query = '?action=query&meta=siteinfo&siprop=general|namespaces|namespacealiases|interwikimap|extensions&format=json'
    getcacheinfo = WikiDB.get_wikiinfo(link)
    if getcacheinfo and ((datetime.datetime.strptime(getcacheinfo[1], "%Y-%m-%d %H:%M:%S") + datetime.timedelta(
            hours=8)).timestamp() - datetime.datetime.now().timestamp()) > - 43200:
        return link, json.loads(getcacheinfo[0])['query']['general']['sitename']
    try:
        api = re.match(r'(https?://.*?/api.php$)', link)
        wlink = api.group(1)
        json1 = json.loads(await get_data(api.group(1) + query, 'json'))
    except:
        try:
            getpage = await get_data(link, 'text')
            m = re.findall(r'(?im)<\s*link\s*rel="EditURI"\s*type="application/rsd\+xml"\s*href="([^>]+?)\?action=rsd"\s*/\s*>', getpage)
            if m:
                api = m[0]
                if api.startswith('//'):
                    api = link.split('//')[0] + api
                getcacheinfo = WikiDB.get_wikiinfo(api)
                if getcacheinfo and (
                        (datetime.datetime.strptime(getcacheinfo[1], "%Y-%m-%d %H:%M:%S") + datetime.timedelta(
                                hours=8)).timestamp() - datetime.datetime.now().timestamp()) > - 43200:
                    return api, json.loads(getcacheinfo[0])['query']['general']['sitename']
                json1 = await get_data(api + query, 'json')
                wlink = api
        except aiohttp.ClientTimeout:
            return False, 'Timeout'
        except Exception as e:
            return False, str(e)
    WikiDB.update_wikiinfo(wlink, json.dumps(json1))
    wikiname = json1['query']['general']['sitename']
    extensions = json1['query']['extensions']
    extlist = []
    for ext in extensions:
        extlist.append(ext['name'])
    print(extlist)
    if 'TextExtracts' not in extlist:
        wikiname = wikiname + '\n警告：此wiki没有启用TextExtracts扩展，返回的页面预览内容将为未处理的原始Wikitext文本。'

    return wlink, wikiname