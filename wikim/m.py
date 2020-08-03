import copy
import requests
import json
import re
import asyncio
import urllib
async def m(lang,str1):
    if lang =='en':
        metaurl = 'https://minecraft.gamepedia.com/api.php?action=query&format=json&prop=info&inprop=url&redirects&titles='
        l = 'https://minecraft.gamepedia.com/'
    else:
        metaurl = 'https://minecraft-'+lang+'.gamepedia.com/api.php?action=query&format=json&prop=info&inprop=url&redirects&titles='
        l = 'https://minecraft-'+lang+'.gamepedia.com/'
    try:
        pagename = str1
        url = metaurl+pagename
        metatext = requests.get(url,timeout=5)
        try:
            file = json.loads(metatext.text)
            try:
                x = file['query']['pages']
                y = sorted(x.keys())[0]
            except Exception:
                return('发生错误：请检查您输入的标题是否正确。')
            
            if  int(y) == -1:
                if 'invalid' in x['-1']:
                    rs = re.sub('The requested page title contains invalid characters:','请求的页面标题包含非法字符：',x['-1']['invalidreason'])
                    return('发生错误：“'+rs+'”。')
                else:
                    if 'missing' in x['-1']:
                        try:
                            if lang =='en':
                                searchurl = 'https://minecraft.gamepedia.com/api.php?action=query&generator=search&gsrsearch='+str1+'&gsrsort=just_match&gsrenablerewrites&prop=info&gsrlimit=1&format=json'
                            else:
                                searchurl = 'https://minecraft-'+lang+'.gamepedia.com/api.php?action=query&generator=search&gsrsearch='+str1+'&gsrsort=just_match&gsrenablerewrites&prop=info&gsrlimit=1&format=json'
                            f = requests.get(searchurl)
                            g = json.loads(f.text)
                            j=g['query']['pages']
                            b = sorted(j.keys())[0]
                            m = j[b]['title']
                            return ('找不到条目，您是否要找的是：'+m+'？')
                        except Exception:
                            return('找不到条目。')
                    else:
                        return ('您要的'+pagename+'：'+l+urllib.parse.quote(pagename.encode('UTF-8')))
            else:
                try:
                    z = x[y]['fullurl']
                    if lang =='en':
                        h = re.match(r'https://minecraft.gamepedia.com/(.*)', z, re.M | re.I)
                        texturl = 'https://minecraft.gamepedia.com/api.php?action=query&prop=extracts&exsentences=1&&explaintext&exsectionformat=wiki&format=json&titles=' + h.group(1)
                    else:
                        h = re.match(r'https://minecraft-(.*).gamepedia.com/(.*)', z, re.M | re.I)
                        texturl = 'https://minecraft-'+h.group(1)+'.gamepedia.com/api.php?action=query&prop=extracts&exsentences=1&&explaintext&exsectionformat=wiki&format=json&titles='+h.group(2)
                    textt = requests.get(texturl,timeout=5)
                    e = json.loads(textt.text)
                    r = e['query']['pages'][y]['extract']
                    try:
                        s = re.match(r'.*(\#.*)',str1)
                        z = x[y]['fullurl'] + urllib.parse.quote(s.group(1).encode('UTF-8'))
                    except Exception:
                        z = x[y]['fullurl']
                    n = re.match(r'https://.*?/(.*)',z)
                    k = urllib.parse.unquote(n.group(1),encoding='UTF-8')
                    k = re.sub('_',' ',k)
                    if k == str1:
                        xx = re.sub('\n$', '', z + '\n' + r)
                    else:
                        xx = re.sub('\n$', '', '\n('+str1 +' -> '+k+')\n'+z + '\n' + r)
                    return('您要的'+pagename+"："+xx)
                except Exception:
                    try:
                        s = re.match(r'.*(\#.*)',str1)
                        z = x[y]['fullurl'] + urllib.parse.quote(s.group(1).encode('UTF-8'))
                    except Exception:
                        z = x[y]['fullurl']
                    n = re.match(r'https://.*?/(.*)',z)
                    k = urllib.parse.unquote(n.group(1),encoding='UTF-8')
                    k = re.sub('_',' ',k)
                    if k == str1:
                        zz = z
                    else:
                        zz = ('\n('+str1 +' -> '+k+')\n'+z)
                    return('您要的'+pagename+"："+zz)
        except Exception:
            return('发生错误：内容非法。')
    except Exception as e:
        return('发生错误：'+str(e))