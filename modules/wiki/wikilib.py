import aiohttp
import re
import traceback
import urllib

from modules.interwikilist import iwlist, iwlink


async def get_data(url: str, fmt: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as req:
            if hasattr(req, fmt):
                return await getattr(req, fmt)()
            else:
                raise ValueError(f"NoSuchMethod: {fmt}")


async def wiki1(wikilink, pagename):
    print(pagename)
    getlinkurl = wikilink + 'api.php?action=query&format=json&prop=info&inprop=url&redirects&titles=' + pagename
    print(getlinkurl)
    file = await get_data(getlinkurl, "json")
    try:
        pages = file['query']['pages']
        pageid = sorted(pages.keys())[0]
        if int(pageid) == -1:
            if 'invalid' in pages['-1']:
                rs = re.sub('The requested page title contains invalid characters:', '请求的页面标题包含非法字符：',
                            pages['-1']['invalidreason'])
                return ('发生错误：“' + rs + '”。')
            else:
                if 'missing' in pages['-1']:
                    try:
                        try:
                            searchurl = wikilink + 'api.php?action=query&generator=search&gsrsearch=' + pagename + '&gsrsort=just_match&gsrenablerewrites&prop=info&gsrlimit=1&format=json'
                            getsecjson = await get_data(searchurl, "json")
                            secpages = getsecjson['query']['pages']
                            secpageid = sorted(secpages.keys())[0]
                            sectitle = secpages[secpageid]['title']
                            return ('找不到条目，您是否要找的是：' + sectitle + '？')
                        except Exception:
                            searchurl = wikilink + 'api.php?action=query&list=search&srsearch=' + pagename + '&srwhat=text&srlimit=1&srenablerewrites=&format=json'
                            getsecjson = await get_data(searchurl, "json")
                            sectitle = getsecjson['query']['search'][0]['title']
                            return ('找不到条目，您是否要找的是：' + sectitle + '？')
                    except Exception:
                        return ('找不到条目。')
                else:
                    return ('您要的' + pagename + '：' + wikilink + urllib.parse.quote(pagename.encode('UTF-8')))
        else:
            getfullurl = pages[pageid]['fullurl']
            geturlpagename = re.match(r'https?://.*?/(?:index.php/|wiki/|)(.*)', getfullurl, re.M | re.I)
            try:
                descurl = getlinkurl + '/api.php?action=query&prop=extracts&exsentences=1&&explaintext&exsectionformat=wiki&format=json&titles=' + geturlpagename.group(
                    1)
                loadtext = await get_data(descurl, "json")
                desc = loadtext['query']['pages'][pageid]['extract']
            except Exception:
                desc = ''
            try:
                section = re.match(r'.*(\#.*)', pagename)
                getfullurl = pages[pageid]['fullurl'] + urllib.parse.quote(section.group(1).encode('UTF-8'))
            except Exception:
                getfullurl = pages[pageid]['fullurl']
            getfinalpagename = re.match(r'https?://.*?/(?:index.php/|wiki/|)(.*)', getfullurl)
            finalpagename = urllib.parse.unquote(getfinalpagename.group(1), encoding='UTF-8')
            finalpagename = re.sub('_', ' ', finalpagename)
            if finalpagename == pagename:
                rmlstlb = re.sub('\n$', '', getfullurl + '\n' + desc)
            else:
                rmlstlb = re.sub('\n$', '', '\n（重定向[' + pagename + '] -> [' + finalpagename + ']）\n' + getfullurl + '\n' + desc)
            rmlstlb = re.sub('\n\n', '\n', rmlstlb)
            rmlstlb = re.sub('\n\n', '\n', rmlstlb)
            try:
                rm5lline = re.findall(r'.*\n.*\n.*\n.*\n.*\n',rmlstlb)
                result = rm5lline[0] + '...行数过多已截断。'
            except Exception:
                result = rmlstlb
            return ('您要的' + pagename + "：" + result)
    except Exception:
        try:
            matchinterwiki = re.match(r'(.*?):(.*)', pagename)
            interwiki = matchinterwiki.group(1)
            if interwiki in iwlist():
                return (await wiki2(interwiki, matchinterwiki.group(2)))
            else:
                return ('发生错误：内容非法。')
        except Exception as e:
            traceback.print_exc()
            return ('发生错误：' + str(e))


async def wiki2(interwiki, str1):
    try:
        url = iwlink(interwiki)
        return (await wiki1(url, str1))
    except Exception as e:
        traceback.print_exc()
        return (str(e))
