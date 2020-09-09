import re
import traceback
import urllib

import aiohttp

from modules.interwikilist import iwlist, iwlink


async def get_data(url: str, fmt: str):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as req:
                if hasattr(req, fmt):
                    return await getattr(req, fmt)()
                else:
                    raise ValueError(f"NoSuchMethod: {fmt}")
        except Exception:
            traceback.print_exc()



async def getpage(wikilink, pagename):
    getlinkurl = wikilink + 'api.php?action=query&format=json&prop=info&inprop=url&redirects&titles=' + pagename
    getpage = await get_data(getlinkurl, "json")
    return getpage


async def parsepageid(getpage):
    pageraw = getpage['query']['pages']
    pagelist = iter(pageraw)
    pageid = pagelist.__next__()
    return pageid


async def researchpage(wikilink, pagename, interwiki):
    try:
        searchurl = wikilink + 'api.php?action=query&generator=search&gsrsearch=' + pagename + '&gsrsort=just_match&gsrenablerewrites&prop=info&gsrlimit=1&format=json'
        getsecjson = await get_data(searchurl, "json")
        secpageid = await parsepageid(getsecjson)
        sectitle = getsecjson['query']['pages'][secpageid]['title']
        if interwiki == '':
            target = ''
        else:
            target = f'{interwiki}:'
        return f'[wait]找不到条目，您是否要找的是：[[{target}{sectitle}]]？'
    except Exception:
        try:
            searchurl = wikilink + 'api.php?action=query&list=search&srsearch=' + pagename + '&srwhat=text&srlimit=1&srenablerewrites=&format=json'
            getsecjson = await get_data(searchurl, "json")
            sectitle = getsecjson['query']['search'][0]['title']
            if interwiki == '':
                target = ''
            else:
                target = f'{interwiki}:'
            return f'[wait]找不到条目，您是否要找的是：[[{target}{sectitle}]]？'
        except Exception:
            return '找不到条目。'


async def nullpage(wikilink, pagename, interwiki, psepgraw):
    if 'invalid' in psepgraw:
        rs1 = re.sub('The requested page title contains invalid characters:', '请求的页面标题包含非法字符：',
                     psepgraw['invalidreason'])
        rs = '发生错误：“' + rs1 + '”。'
        rs = re.sub('".”', '"”', rs)
        return rs
    if 'missing' in psepgraw:
        return await researchpage(wikilink, pagename, interwiki)
    return wikilink + urllib.parse.quote(pagename.encode('UTF-8'))


async def getdesc(wikilink, pagename):
    try:
        descurl = wikilink + 'api.php?action=query&prop=extracts&exsentences=1&&explaintext&exsectionformat=wiki' \
                             '&format=json&titles=' + pagename
        loadtext = await get_data(descurl, "json")
        pageid = await parsepageid(loadtext)
        desc = loadtext['query']['pages'][pageid]['extract']
    except Exception:
        desc = ''
    return desc


async def getfirstline(wikilink, pagename):
    try:
        descurl = wikilink + f'api.php?action=parse&page={pagename}&prop=wikitext&section=1&format=json'
        loaddesc = await get_data(descurl, 'json')
        descraw = loaddesc['parse']['wikitext']['*']
        cutdesc = re.findall(r'(.*(?:!|\?|\.|;|！|？|。|；))', descraw, re.S | re.M)
        desc = cutdesc[0]
    except Exception:
        desc = ''
    return desc


async def step1(wikilink, pagename, interwiki, igmessage=False, template=False):
    pageraw = await getpage(wikilink, pagename)
    pageid = await parsepageid(pageraw)
    psepgraw = pageraw['query']['pages'][pageid]
    if pageid == '-1':
        if igmessage == False:
            if template == True:
                pagename = re.sub(r'^Template:', '', pagename)
                return f'提示：[Template:{pagename}]不存在，已自动回滚搜索页面。\n' + await step1(wikilink, pagename, interwiki,
                                                                                 igmessage)
            return await nullpage(wikilink, pagename, interwiki, psepgraw)
    else:
        return await step2(wikilink, pagename, interwiki, psepgraw)


async def step2(wikilink, pagename, interwiki, psepgraw):
    fullurl = psepgraw['fullurl']
    geturlpagename = re.match(r'(https?://.*?/(?:index.php/|wiki/|.*wiki/|))(.*)', fullurl, re.M | re.I)
    desc = await getdesc(wikilink, geturlpagename.group(2))
    if desc == '':
        desc = await getfirstline(wikilink, geturlpagename.group(2))
    try:
        section = re.match(r'.*(\#.*)', pagename)
        finpgname = geturlpagename.group(2) + urllib.parse.quote(section.group(1).encode('UTF-8'))
        fullurl = psepgraw['fullurl'] + urllib.parse.quote(section.group(1).encode('UTF-8'))
    except Exception:
        finpgname = geturlpagename.group(2)
    finpgname = urllib.parse.unquote(finpgname)
    finpgname = re.sub('_', ' ', finpgname)
    if finpgname == pagename:
        rmlstlb = re.sub('\n$', '', fullurl + '\n' + desc)
    else:
        rmlstlb = re.sub('\n$', '',
                         f'\n（重定向[{pagename}] -> [{finpgname}]）\n{fullurl}\n{desc}')
    rmlstlb = re.sub('\n\n', '\n', rmlstlb)
    rmlstlb = re.sub('\n\n', '\n', rmlstlb)
    try:
        rm5lline = re.findall(r'.*\n.*\n.*\n.*\n.*\n', rmlstlb)
        result = rm5lline[0] + '...行数过多已截断。'
    except Exception:
        result = rmlstlb
    if interwiki != '':
        pagename = interwiki + ':' + pagename
    return f'您要的{pagename}：{result}'


async def wiki(wikilink, pagename, interwiki='', igmessage=False, template=False):
    print(wikilink)
    print(pagename)
    print(interwiki)
    try:
        matchinterwiki = re.match(r'(.*?):(.*)', pagename)
        if matchinterwiki:
            if matchinterwiki.group(1) in iwlist():
                return await wiki(iwlink(matchinterwiki.group(1)), matchinterwiki.group(2), matchinterwiki.group(1),
                                  igmessage, template)
            else:
                return await step1(wikilink, pagename, interwiki, igmessage, template)
        else:
            return await step1(wikilink, pagename, interwiki, igmessage, template)
    except Exception as e:
        traceback.print_exc()
        if igmessage == False:
            return f'发生错误：{str(e)}'


if __name__ == '__main__':
    import asyncio

    a = asyncio.run(wiki('https://minecraft-zh.gamepedia.com/', 'zh:en:zh:海晶石'))
    print(a)
