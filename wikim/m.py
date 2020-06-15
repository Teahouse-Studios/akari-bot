import copy
import requests
import json
import re
import asyncio
import urllib
async def m(lang,str1):
    if lang =='en':
        metaurl = 'https://minecraft.gamepedia.com/api.php?action=query&format=json&prop=info&inprop=url&redirects&titles='
    else:
        metaurl = 'https://minecraft-'+lang+'.gamepedia.com/api.php?action=query&format=json&prop=info&inprop=url&redirects&titles='
    pagename = str1
    try:
        url = metaurl+pagename
        metatext = requests.get(url,timeout=5)
        file = json.loads(metatext.text)
        try:
            x = file['query']['pages']
            y = sorted(x.keys())[0]
            if  int(y) == -1:
                if ('missing' in x[y]):
                    return ('您要的'+pagename+'：'+'https://'+path+'.gamepedia.com/'+urllib.parse.quote(pagename.encode('UTF-8')))
                else:
                    try:
                        if lang =='en':
                            h = re.match(r'https://minecraft.gamepedia.com/(.*)', z, re.M | re.I)
                            searchurl = 'https://minecraft.gamepedia.com/api.php?action=query&generator=search&gsrsearch='+h.group(1)+'&gsrsort=just_match&gsrenablerewrites&prop=info&gsrlimit=1&format=json'
                        else:
                            h = re.match(r'https://minecraft-(.*).gamepedia.com/(.*)', z, re.M | re.I)
                            searchurl = 'https://minecraft-'+h.group(1)+'.gamepedia.com/api.php?action=query&generator=search&gsrsearch='+h.group(2)+'&gsrsort=just_match&gsrenablerewrites&prop=info&gsrlimit=1&format=json'
                        f = requests.get(searchurl)
                        g = json.loads(f.text)
                        j=g['query']['pages']
                        b = sorted(j.keys())[0]
                        m = j[b]['title']
                        return ('找不到条目，您是否要找的是：'+m+'？')
                    except Exception:
                        return('找不到条目。')
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
                    xx = re.sub('\n$', '', z + '\n' + r)
                    return('您要的'+pagename+"："+xx)
                except Exception:
                    return('您要的'+pagename+"："+z)
        except  Exception:
            return('发生错误：内容非法。')
    except  Exception as e:
        return('发生错误：'+str(e))