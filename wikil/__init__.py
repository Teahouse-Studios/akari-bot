import requests
import json
import re
import urllib
async def im(str1):
    try:
        pipe = re.match(r'(.*?)\|.*',str1)
        str1 = pipe.group(1)
    except Exception:
        str1 = str1
    try:
        d = re.match(r'(.*?):(.*)',str1)
        w = d.group(1)
        if (w == "cs" or w == "de" or w == "el" or w == "es" or w == "fr" or w == "hu" or w == "it" or w == "ja" or w == "ko" or w == "nl" or w == "pl" or w == "pt" or w == "ru" or w == "th" or w == "tr" or w == "uk" or w == "zh"):
            c = 'minecraft-'+w
            pagename = d.group(2)
        elif w == "en":
            c = 'minecraft'
            pagename = d.group(2)
        else:
            c = 'minecraft-zh'
            pagename = str1
    except Exception:
        c = 'minecraft-zh'
        pagename = str1
    metaurl = 'https://'+c+'.gamepedia.com/api.php?action=query&format=json&prop=info&inprop=url&redirects&titles='
    url1 = 'https://'+c+'.gamepedia.com/'
    try:
        url = metaurl+pagename
        metatext = requests.get(url,timeout=5)
        file = json.loads(metatext.text)
        try:
            x = file['query']['pages']
            y = sorted(x.keys())[0]
            if  int(y) == -1:
                if 'missing' in x['-1']:
                    try:                
                        searchurl = url1+'api.php?action=query&generator=search&gsrsearch=' + pagename + '&gsrsort=just_match&gsrenablerewrites&prop=info&gsrlimit=1&format=json'
                        f = requests.get(searchurl)
                        g = json.loads(f.text)
                        j = g['query']['pages']
                        b = sorted(j.keys())[0]
                        m = j[b]['title']
                        return ('提示：您要找的'+ pagename + '不存在，要找的页面是' + m + '吗？')
                    except Exception:
                        return ('提示：找不到'+ pagename+'。')
                else:
                    return (url1+urllib.parse.quote(pagename.encode('UTF-8')))
            else:
                z = x[y]['fullurl']
                h = re.match(r'https://(.*).gamepedia.com/(.*)', z, re.M | re.I)
                texturl = 'https://'+h.group(1)+'.gamepedia.com/api.php?action=query&prop=extracts&exsentences=1&&explaintext&exsectionformat=wiki&format=json&titles='+h.group(2)
                textt = requests.get(texturl,timeout=5)
                e = json.loads(textt.text)
                r = e['query']['pages'][y]['extract']
                try:
                    b = re.match(r'.*(\#.*)',str1)
                    z = x[y]['fullurl']+urllib.parse.quote(b.group(1).encode('UTF-8'))
                except Exception:
                    z = x[y]['fullurl']
                k = urllib.parse.unquote(h.group(2),encoding='UTF-8')
                k = re.sub('_',' ',k)
                if k == str1:
                    xx = re.sub('\n$','',z+'\n'+r)
                else:
                    xx = re.sub('\n$','','('+str1+' -> '+k+')\n'+z+'\n'+r)
                return(xx)
        except  Exception as e:
            return('发生错误：'+str(e))
    except  Exception as e:
        return('发生错误：'+str(e))