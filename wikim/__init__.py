import re
from .m import m
from .wikilib import Wiki
import asyncio
import traceback
async def wikim(str1):
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
            if (w == "cs" or w == "de" or w == "el" or w == "es" or w == "fr" or w == "hu" or w == "it" or w == "ja" or w == "ko" or w == "nl" or w == "pl" or w == "pt" or w == "ru" or w == "th" or w == "tr" or w == "uk" or w == "zh"):
                return(await m(q.group(1),q.group(2)))
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
                    d = re.match(r'(.*?):(.*)',q.group(1))
                    x = d.group(2)
                    w = str.lower(d.group(1))
                    if (w == "cs" or w == "de" or w == "el" or w == "es" or w == "fr" or w == "hu" or w == "it" or w == "ja" or w == "ko" or w == "nl" or w == "pl" or w == "pt" or w == "ru" or w == "th" or w == "tr" or w == "uk" or w == "zh"):
                        try:
                            metaurl = 'https://minecraft-' + w + '.gamepedia.com'
                            return (await Wiki(metaurl, x))
                        except  Exception as e:
                            traceback.print_exc()
                            return ('发生错误：' + str(e))
                    elif w == 'Wikipedia' or w == 'wikipedia':
                        return('暂不支持Wikipedia查询。')
                    elif w == 'Moegirl' or w == 'moegirl' or w=='moe':
                        try:
                            metaurl = 'https://zh.moegirl.org.cn'
                            return (await Wiki(metaurl, x))
                        except Exception as e:
                            return ('发生错误：' + str(e))
                    elif w =='arcaea' or w == 'arc':
                        try:
                            metaurl = 'https://wiki.arcaea.cn/'
                            return (await Wiki(metaurl, x))
                        except Exception as e:
                            return ('发生错误：' + str(e))
                    else:
                        try:
                            metaurl = 'https://minecraft.gamepedia.com'
                            return (await Wiki(metaurl, q.group(1)))
                        except  Exception as e:
                            traceback.print_exc()
                            return ('发生错误：' + str(e))
                except Exception:
                    return(await m('en',q.group(1)))