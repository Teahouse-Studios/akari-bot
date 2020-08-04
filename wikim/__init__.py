import re
from .wikilib import Wiki,wiki2
import asyncio
import traceback
from interwikilist import iwlist,iwlink
async def wikim(str1,group = 0):
    if str1.find(' -h')!=-1:
        return('''~wiki ~<site> <pagename> - 从指定Gamepedia站点中输出条目链接。
~wiki <lang>:<pagename>, ~wiki-<lang> <pagename> - 从指定语言中的Minecraft Wiki中输出条目链接。
~wiki <pagename> - 从Minecraft Wiki（英文）中输出条目链接。''')
    else:
        try:
            b = re.sub(r'^Wiki','wiki',str1)
        except:
            b = str1
        try:
            q = re.match(r'^wiki-(.*?) (.*)',b)
            w = q.group(1)
            print(w)
            if w in iwlist():
                return(await wiki2(q.group(1),q.group(2)))
            else:
                return('未知语言，请使用~wiki -h查看帮助。')
        except:
            q = re.match(r'^wiki (.*)',b)
            try:
                s = re.match(r'~(.*?) (.*)',q.group(1))
                metaurl = 'https://' + s.group(1) + '.gamepedia.com'
                return (await Wiki(metaurl,s.group(2)))
            except:
                try:
                    if group == 250500369:
                        x = q.group(1)
                        metaurl = 'https://wiki.arcaea.cn'
                        return (await Wiki(metaurl, x))
                    else:
                        d = re.match(r'(.*?):(.*)',q.group(1))
                        x = d.group(2)
                        w = str.lower(d.group(1))
                        if w in iwlist():
                            try:
                                metaurl = iwlink(w)
                                return (await Wiki(metaurl, x))
                            except  Exception as e:
                                traceback.print_exc()
                                return ('发生错误：' + str(e))
                        elif w == 'Wikipedia' or w == 'wikipedia':
                            return('暂不支持Wikipedia查询。')
                        else:
                            try:
                                metaurl = 'https://minecraft.gamepedia.com'
                                return (await Wiki(metaurl, x))
                            except  Exception as e:
                                traceback.print_exc()
                                return ('发生错误：' + str(e))
                except Exception:
                    return(await wiki2('en',q.group(1)))