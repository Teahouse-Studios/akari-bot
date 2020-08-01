import json
import re
import requests
import urllib
import traceback
async def Wiki(path1,pagename):
    metaurl = path1 +'/api.php?action=query&format=json&prop=info&inprop=url&redirects&titles=' + pagename
    print(metaurl)
    metatext = requests.get(metaurl, timeout=10)
    file = json.loads(metatext.text)
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
                            searchurl = path1+'/api.php?action=query&generator=search&gsrsearch=' + pagename + '&gsrsort=just_match&gsrenablerewrites&prop=info&gsrlimit=1&format=json'
                            f = requests.get(searchurl)
                            g = json.loads(f.text)
                            j = g['query']['pages']
                            b = sorted(j.keys())[0]
                            m = j[b]['title']
                            return ('找不到条目，您是否要找的是：' + m +'？')
                        except Exception:
                            searchurl = '/api.php?action=query&list=search&srsearch='+pagename+'&srwhat=text&srlimit=1&srenablerewrites=&format=json'
                            f = requests.get(searchurl)
                            g = json.loads(f.text)
                            j = g['query']['search']
                            b = sorted(j.keys())[0]
                            m = j[b]['title']
                            return ('找不到条目，您是否要找的是：' + m +'？')
                    except Exception:
                        return ('找不到条目。')
                else:
                    return ('您要的'+pagename+'：'+path1+'/'+urllib.parse.quote(pagename.encode('UTF-8')))
        else:
            z = x[y]['fullurl']
            if z.find('index.php') != -1 or z.find('Index.php') !=-1:
                h = re.match(r'https?://.*/.*/(.*)', z, re.M | re.I)
            else:
                h = re.match(r'https?://.*/(.*)', z, re.M | re.I)
            try:
                texturl = metaurl + '/api.php?action=query&prop=extracts&exsentences=1&&explaintext&exsectionformat=wiki&format=json&titles=' + h.group(1)
                gettext = requests.get(texturl, timeout=10)
                loadtext = json.loads(gettext.text)
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
                xx = re.sub('\n$', '', '\n('+pagename +' -> '+k+')\n'+z + '\n' + v)
            return('您要的'+pagename+"："+xx)
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
            traceback.print_exc()
            return('发生错误：'+str(e))