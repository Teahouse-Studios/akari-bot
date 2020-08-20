import aiohttp
import re
import traceback
import urllib


async def get_data(url: str, fmt: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as req:
            if hasattr(req, fmt):
                return await getattr(req, fmt)()
            else:
                raise ValueError(f"NoSuchMethod: {fmt}")


async def wi(wikiurl, interwiki, pagename, itw='f', ignoremessage='f', template='f'):
    metaurl = wikiurl + 'api.php?action=query&format=json&prop=info&inprop=url&redirects&titles='
    try:
        linkurl = metaurl + pagename
        file = await get_data(linkurl, "json")
        try:
            try:
                pages = file['query']['pages']
                pageid = sorted(pages.keys())[0]
            except Exception:
                if ignoremessage == 'f':
                    return '发生错误：请检查您输入的标题是否正确。'
                else:
                    pass
            if int(pageid) == -1:
                if 'invalid' in pages['-1']:
                    if ignoremessage == 'f':
                        rs = re.sub('The requested page title contains invalid characters:', '请求的页面标题包含非法字符：',
                                    pages['-1']['invalidreason'])
                        return '发生错误：“' + rs + '”。'
                    else:
                        pass
                else:
                    if 'missing' in pages['-1']:
                        if template == 'f':
                            if ignoremessage == 'f':
                                try:
                                    try:
                                        searchurl = wikiurl + 'api.php?action=query&generator=search&gsrsearch=' + pagename + '&gsrsort=just_match&gsrenablerewrites&prop=info&gsrlimit=1&format=json'
                                        getsecjson = await get_data(searchurl, "json")
                                        secpages = getsecjson['query']['pages']
                                        secpageid = sorted(secpages.keys())[0]
                                        sectitle = secpages[secpageid]['title']
                                        if itw == 't':
                                            sectitle = interwiki + ':' + sectitle
                                            pagename = interwiki + ':' + pagename
                                        return '提示：您要找的' + pagename + '不存在，要找的页面是' + sectitle + '吗？'
                                    except Exception:
                                        searchurl = wikiurl + 'api.php?action=query&list=search&srsearch=' + pagename + '&srwhat=text&srlimit=1&srenablerewrites=&format=json '
                                        getsecjson = await get_data(searchurl, "json")
                                        sectitle = getsecjson['query']['search'][0]['title']
                                        if itw == 't':
                                            sectitle = interwiki + ':' + sectitle
                                            pagename = interwiki + ':' + pagename
                                        return '提示：您要找的' + pagename + '不存在，要找的页面是' + sectitle + '吗？'
                                except Exception:
                                    traceback.print_exc()
                                    if itw == 't':
                                        pagename = interwiki + ':' + pagename
                                    return '提示：找不到' + pagename + '。'
                            else:
                                pass
                        else:
                            pagename = re.sub('Template:', '', pagename)
                            pagename = re.sub('template:', '', pagename)
                            return ('提示：[' + pagename + ']不存在，已自动回滚搜索页面。\n' + await wi(wikiurl, interwiki, pagename, itw, ignoremessage,
                                                                                       template='f'))
                    else:
                        return wikiurl + urllib.parse.quote(pagename.encode('UTF-8'))
            else:
                try:
                    fullurl = pages[pageid]['fullurl']
                    matchurl = re.match(r'https?://.*?/(?:index.php/|wiki/|)(.*)', fullurl, re.M | re.I)
                    texturl = wikiurl + 'api.php?action=query&prop=extracts&exsentences=1&&explaintext&exsectionformat=wiki&format=json&titles=' + matchurl.group(
                        1)
                    getdesc = await get_data(texturl, "json")
                    desc = getdesc['query']['pages'][pageid]['extract']
                except:
                    desc = ''
                try:
                    section = re.match(r'.*(\#.*)', pagename)
                    fullurl = pages[pageid]['fullurl'] + urllib.parse.quote(section.group(1).encode('UTF-8'))
                except Exception:
                    fullurl = pages[pageid]['fullurl']
                matchfinalurl = re.match(r'https?://.*?/(?:index.php/|wiki/|)(.*)', fullurl, re.M | re.I)
                finalpagename = urllib.parse.unquote(matchfinalurl.group(1), encoding='UTF-8')
                finalpagename = re.sub('_', ' ', finalpagename)
                if itw == 't':
                    finalpagename = interwiki + ':' + finalpagename
                    pagename = interwiki + ':' + pagename
                if finalpagename == pagename:
                    rmlstlb = re.sub('\n$', '', fullurl + '\n' + desc)
                else:
                    rmlstlb = re.sub('\n$', '', '（重定向[' + pagename + ']至[' + finalpagename + ']）\n' + fullurl + '\n' + desc)
                rmlstlb = re.sub('\n\n', '\n', rmlstlb)
                rmlstlb = re.sub('\n\n', '\n', rmlstlb)
                rmlstlb = re.sub('\n\n\n', '\n', rmlstlb)
                rmlstlb = re.sub('\n\n\n\n', '\n', rmlstlb)
                try:
                    rm5lline = re.findall(r'.*\n.*\n.*\n.*\n.*\n', rmlstlb)
                    result = rm5lline[0] + '\n...行数过多已截断。'
                except:
                    result = rmlstlb
                return result
        except  Exception as getdesc:
            traceback.print_exc()
            if ignoremessage == 'f':
                return '发生错误：' + str(getdesc)
            else:
                pass
    except  Exception as getdesc:
        traceback.print_exc()
        if ignoremessage == 'f':
            return '发生错误：' + str(getdesc)
        else:
            pass
