import requests
import json
import re
import urllib
import traceback
async def wi(c,w,pagename,itw = 'f',ignoremessage = 'f',template = 'f'):
    str1 = pagename
    metaurl = 'https://'+c+'/api.php?action=query&format=json&prop=info&inprop=url&redirects&titles='
    url1 = 'https://'+c+'/'
    try:
        url = metaurl+pagename
        metatext = requests.get(url,timeout=5)
        file = json.loads(metatext.text)
        try:
            try:
                x = file['query']['pages']
                y = sorted(x.keys())[0]
            except Exception:
                if ignoremessage == 'f':
                    return('发生错误：请检查您输入的标题是否正确。')
                else:
                    pass   
            if  int(y) == -1:
                if 'invalid' in x['-1']:
                    if ignoremessage == 'f':
                        rs = re.sub('The requested page title contains invalid characters:','请求的页面标题包含非法字符：',x['-1']['invalidreason'])
                        return('发生错误：“'+rs+'”。')
                    else:
                        pass
                else:
                    if 'missing' in x['-1']:
                        if template == 'f':
                            if ignoremessage == 'f':
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
                                    traceback.print_exc()
                                    if itw == 't':
                                        pagename = w+':'+pagename
                                    return ('提示：找不到'+ pagename+'。')
                            else:
                                pass
                        else:
                            name = re.sub('Template:','',pagename)
                            name = re.sub('template:','',name)
                            return('提示：['+pagename+']不存在，已自动回滚搜索页面。\n'+await wi(c,w,name,itw,ignoremessage,template='f'))
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
                    xx = re.sub('\n$','','（重定向['+str1+']至['+k+']）\n'+z+'\n'+r)
                return(xx)
        except  Exception as e:
            traceback.print_exc()
            if ignoremessage == 'f':
                return('发生错误：'+str(e))
            else:
                pass
    except  Exception as e:
        traceback.print_exc()
        if ignoremessage == 'f':
            return('发生错误：'+str(e))
        else:
            pass