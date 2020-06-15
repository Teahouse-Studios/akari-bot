import json
import re
import requests
import urllib
def Wiki(path1,pagename):
    metaurl = path1 +'/api.php?action=query&format=json&prop=info&inprop=url&redirects&titles=' + pagename
    metatext = requests.get(metaurl, timeout=10)
    file = json.loads(metatext.text)
    try:
        x = file['query']['pages']
        y = sorted(x.keys())[0]
        if int(y) == -1:
            if 'missing' in x['-1']:
                try:                
                    searchurl = path1+'/api.php?action=query&generator=search&gsrsearch=' + pagename + '&gsrsort=just_match&gsrenablerewrites&prop=info&gsrlimit=1&format=json'
                    f = requests.get(searchurl)
                    g = json.loads(f.text)
                    j = g['query']['pages']
                    b = sorted(j.keys())[0]
                    m = j[b]['title']
                    return ('找不到条目，您是否要找的是：' + m +'？')
                except Exception:
                    return ('找不到条目。')
            else:
                return ('您要的'+pagename+'：'+'https://'+path1+'.gamepedia.com/'+urllib.parse.quote(pagename.encode('UTF-8')))
        else:
            try:
                z = x[y]['fullurl']
                h = re.match(r'https://.*/(.*)', z, re.M | re.I)
                texturl = metaurl + '/api.php?action=query&prop=extracts&exsentences=1&&explaintext&exsectionformat=wiki&format=json&titles=' + h.group(1)
                gettext = requests.get(texturl, timeout=10)
                loadtext = json.loads(gettext.text)
                v = loadtext['query']['pages'][y]['extract']
                xx = re.sub('\n$', '', z + '\n' + v)
                return('您要的' + pagename + "：" +xx)
            except Exception:
                return('您要的' + pagename + "：" + z)
    except Exception:
        try:
            w = re.match(r'https://.*-(.*).gamepedia.com',path1)
            u = re.sub(w.group(1) + r':', "", pagename)
            i = re.sub(r':.*', "", u)
            print(u)
            print(i)
            if (i == "ftb" or i == "aether" or i == "cs" or i == "de" or i == "el" or i == "en" or i == "es" or i == "fr" or i == "hu" or i == "it" or i == "ja" or i == "ko" or i == "nl" or i == "pl" or i == "pt" or i == "ru" or i == "th" or i == "tr" or i == "uk" or i == "zh"):
                return('检测到多重Interwiki，暂不支持多重Interwiki。')
            else:
                return('发生错误：内容非法。')
        except Exception as e:
            return('发生错误：'+str(e))