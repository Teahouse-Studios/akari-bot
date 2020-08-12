import json
import re
import aiohttp
import urllib
import traceback
from interwikilist import iwlist,iwlink

async def get_data(url: str, fmt: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(url,timeout=aiohttp.ClientTimeout(total=20)) as req:
            if hasattr(req, fmt):
                return await getattr(req, fmt)()
            else:
                raise ValueError(f"NoSuchMethod: {fmt}")


async def wiki1(path1,pagename):
    print(pagename)
    metaurl = path1 +'api.php?action=query&format=json&prop=info&inprop=url&redirects&titles=' + pagename
    print(metaurl)
    file = await get_data(metaurl,"json")
    try:
        x = file['query']['pages']
        y = sorted(x.keys())[0]
        if int(y) == -1:
            if 'invalid' in x['-1']:
                rs = re.sub('The requested page title contains invalid characters:','请求的页面标题包含非法字符：',x['-1']['invalidreason'])
                return('发生错误：“'+rs+'”。')
            else:
                if 'missing' in x['-1']:
                    try:
                        try:
                            searchurl = path1+'api.php?action=query&generator=search&gsrsearch=' + pagename + '&gsrsort=just_match&gsrenablerewrites&prop=info&gsrlimit=1&format=json'
                            g = await get_data(searchurl,"json")
                            j = g['query']['pages']
                            b = sorted(j.keys())[0]
                            m = j[b]['title']
                            return ('找不到条目，您是否要找的是：' + m +'？')
                        except Exception:
                            searchurl = path1+'api.php?action=query&list=search&srsearch='+pagename+'&srwhat=text&srlimit=1&srenablerewrites=&format=json'
                            g = await get_data(searchurl,"json")
                            m = g['query']['search'][0]['title']
                            return ('找不到条目，您是否要找的是：' + m +'？')
                    except Exception:
                        return ('找不到条目。')
                else:
                    return ('您要的'+ pagename +'：'+path1 + urllib.parse.quote(pagename.encode('UTF-8')))
        else:
            z = x[y]['fullurl']
            if z.find('index.php') != -1 or z.find('Index.php') !=-1:
                h = re.match(r'https?://.*/.*/(.*)', z, re.M | re.I)
            else:
                h = re.match(r'https?://.*/(.*)', z, re.M | re.I)
            try:
                texturl = metaurl + '/api.php?action=query&prop=extracts&exsentences=1&&explaintext&exsectionformat=wiki&format=json&titles=' + h.group(1)
                loadtext = await get_data(texturl,"json")
                v = loadtext['query']['pages'][y]['extract']
            except Exception:
                v = ''
            try:
                s = re.match(r'.*(\#.*)',pagename)
                z = x[y]['fullurl'] + urllib.parse.quote(s.group(1).encode('UTF-8'))
            except Exception:
                z = x[y]['fullurl']
            if z.find('index.php') != -1 or z.find('Index.php') !=-1:
                n = re.match(r'https?://.*?/.*/(.*)',z)
            else:
                n = re.match(r'https?://.*?/(.*)',z)
            k = urllib.parse.unquote(n.group(1),encoding='UTF-8')
            k = re.sub('_',' ',k)
            if k == pagename:
                xx = re.sub('\n$', '', z + '\n' + v)
            else:
                xx = re.sub('\n$', '', '\n（重定向['+pagename +']至['+k+']）\n'+z + '\n' + v)
            return('您要的'+pagename+"："+xx)
    except Exception:
        try:
            w = re.match(r'(.*?):(.*)',pagename)
            i = w.group(1)
            if i in iwlist():
                return(await wiki2(i,w.group(2)))
            else:
                return('发生错误：内容非法。')
        except Exception as e:
            traceback.print_exc()
            return('发生错误：'+str(e))


async def wiki2(lang,str1):
    try:
        metaurl = iwlink(lang)
        return(await wiki1(metaurl,str1))
    except Exception as e:
        traceback.print_exc()
        return (str(e))