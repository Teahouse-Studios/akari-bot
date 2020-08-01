import requests
import json
import re
import urllib
import traceback
async def im(str1):
    try:
        pipe = re.match(r'(.*?)\|.*',str1)
        str1 = pipe.group(1)
    except Exception:
        str1 = str1
    try:
        d = re.match(r'(.*?):(.*)',str1)
        w = d.group(1)
        w = str.lower(w)
        if (w == "cs" or w == "de" or w == "el" or w == "es" or w == "fr" or w == "hu" or w == "it" or w == "ja" or w == "ko" or w == "nl" or w == "pl" or w == "pt" or w == "ru" or w == "th" or w == "tr" or w == "uk" or w == "zh"):
            c = 'minecraft-'+w+'.gamepedia.com'
            pagename = d.group(2)
            itw = 't'
        elif w == "en":
            c = 'minecraft.gamepedia.com'
            pagename = d.group(2)
            itw = 't'
        elif w == 'arc' or 'arcaea':
            c = 'wiki.arcaea.cn'
            pagename = d.group(2)
            itw = 't'
        elif w == 'moe' or 'moegirl':
            c = 'zh.moegirl.org.cn'
            pagename = d.group(2)
            itw = 't'
        else:
            c = 'minecraft-zh.gamepedia.com'
            pagename = str1
            itw = 'f'
    except Exception:
        c = 'minecraft-zh.gamepedia.com'
        pagename = str1
        itw = 'f'
    w = d.group(1)
    metaurl = 'https://'+c+'/api.php?action=query&format=json&prop=info&inprop=url&redirects&titles='
    url1 = 'https://'+c+'/'
    try:
        url = metaurl+pagename
        metatext = requests.get(url,timeout=5)
        file = json.loads(metatext.text)
        try:
            x = file['query']['pages']
            y = sorted(x.keys())[0]
            if  int(y) == -1:
                if 'invalid' in x['-1']:
                    rs = re.sub('The requested page title contains invalid characters:','请求的页面标题包含非法字符：',x['-1']['invalidreason'])
                    return('发生错误：“'+rs+'”。')
                else:
                    if 'missing' in x['-1']:
                        try:
                            try:                
                                searchurl = url1+'api.php?action=query&generator=search&gsrsearch=' + pagename + '&gsrsort=just_match&gsrenablerewrites&prop=info&gsrlimit=1&format=json'
                                f = requests.get(searchurl)
                                g = json.loads(f.text)
                                j = g['query']['pages']
                                b = sorted(j.keys())[0]
                                m = j[b]['title']
                                if itw == 't':
                                    m = w+':'+m
                                    pagename = w+':'+pagename
                                return ('提示：您要找的'+ pagename + '不存在，要找的页面是' + m + '吗？')
                            except Exception:
                                searchurl = url1+'api.php?action=query&list=search&srsearch=' + pagename + '&srwhat=text&srlimit=1&srenablerewrites=&format=json'
                                f = requests.get(searchurl)
                                g = json.loads(f.text)
                                m = g['query']['search'][0]['title']
                                if itw == 't':
                                    m = w+':'+m
                                    pagename = w+':'+pagename
                                return ('提示：您要找的'+ pagename + '不存在，要找的页面是' + m + '吗？')
                        except Exception:
                            if itw == 't':
                                pagename = w+':'+pagename
                            return ('提示：找不到'+ pagename+'。')
                    else:
                        return (url1+urllib.parse.quote(pagename.encode('UTF-8')))
            else:
                try:
                    z = x[y]['fullurl']
                    print(z)
                    if z.find('index.php')!=-1 or z.find('Index.php')!=-1:
                        h = re.match(r'https?://(.*?)/.*?/(.*)', z, re.M | re.I)
                    else:
                        h = re.match(r'https?://(.*?)/(.*)', z, re.M | re.I)
                    texturl = 'https://'+h.group(1)+'/api.php?action=query&prop=extracts&exsentences=1&&explaintext&exsectionformat=wiki&format=json&titles='+h.group(2)
                    textt = requests.get(texturl,timeout=5)
                    e = json.loads(textt.text)
                    r = e['query']['pages'][y]['extract']
                except:
                    r = ''
                try:
                    b = re.match(r'.*(\#.*)',str1)
                    z = x[y]['fullurl']+urllib.parse.quote(b.group(1).encode('UTF-8'))
                except Exception:
                    z = x[y]['fullurl']
                k = urllib.parse.unquote(h.group(2),encoding='UTF-8')
                k = re.sub('_',' ',k)
                if itw == 't':
                    k = w+':'+k
                if k == str1:
                    xx = re.sub('\n$','',z+'\n'+r)
                else:
                    xx = re.sub('\n$','','('+str1+' -> '+k+')\n'+z+'\n'+r)
                return(xx)
        except  Exception as e:
            traceback.print_exc()
            return('发生错误：'+str(e))
    except  Exception as e:
        traceback.print_exc()
        return('发生错误：'+str(e))