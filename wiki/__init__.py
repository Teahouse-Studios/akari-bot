import asyncio
import re
import traceback

from help import wikihelp
from interwikilist import iwlist, iwlink
from .wikilib import wiki1, wiki2


async def wiki(str1, group=0):
    if str1.find(' -h') != -1:
        return (await wikihelp())
    else:
        try:
            b = re.sub(r'^Wiki', 'wiki', str1)
        except:
            b = str1
        try:
            q = re.match(r'^wiki-(.*?) (.*)', b)
            w = q.group(1)
            print(w)
            if w in iwlist():
                return (await wiki2(q.group(1), q.group(2)))
            else:
                return ('未知语言，请使用~wiki -h查看帮助。')
        except:
            q = re.match(r'^wiki (.*)', b)
            try:
                s = re.match(r'~(.*?) (.*)', q.group(1))
                metaurl = 'https://' + s.group(1) + '.gamepedia.com'
                return (await wiki1(metaurl, s.group(2)))
            except:
                try:
                    if group == 250500369 or group == 676942198:
                        x = q.group(1)
                        metaurl = 'https://wiki.arcaea.cn/'
                        return (await wiki1(metaurl, x))
                    else:
                        d = re.match(r'(.*?):(.*)', q.group(1))
                        x = d.group(2)
                        w = str.lower(d.group(1))
                        if w in iwlist():
                            try:
                                metaurl = iwlink(w)
                                return (await wiki1(metaurl, x))
                            except  Exception as e:
                                traceback.print_exc()
                                return ('发生错误：' + str(e))
                        elif w == 'Wikipedia' or w == 'wikipedia':
                            return ('暂不支持Wikipedia查询。')
                        else:
                            try:
                                metaurl = 'https://minecraft.gamepedia.com/'
                                return (await wiki1(metaurl, x))
                            except  Exception as e:
                                traceback.print_exc()
                                return ('发生错误：' + str(e))
                except Exception:
                    return (await wiki2('en', q.group(1)))


from .wikitextlib import wi


async def im(str1):
    try:
        pipe = re.match(r'(.*?)\|.*', str1)
        str1 = pipe.group(1)
    except Exception:
        str1 = str1
    str1 = re.sub(r'^:', '', str1)
    try:
        d = re.match(r'(.*?):(.*)', str1)
        w = d.group(1)
        w = str.lower(w)
        if w in iwlist():
            c = iwlink(w)
            pagename = d.group(2)
            itw = 't'
        else:
            c = iwlink('zh')
            pagename = str1
            itw = 'f'
    except Exception:
        c = iwlink('zh')
        pagename = str1
        itw = 'f'
        w = '.'
    return (await wi(c, w, pagename, itw, ignoremessage='f'))


async def imarc(str1):
    try:
        pipe = re.match(r'(.*?)\|.*', str1)
        str1 = pipe.group(1)
    except Exception:
        str1 = str1
    str1 = re.sub(r'^:', '', str1)
    c = 'https://wiki.arcaea.cn/'
    itw = 'f'
    w = '.'
    return (await wi(c, w, str1, itw, ignoremessage='t'))


async def imt(str1):
    try:
        pipe = re.match(r'(.*?)\|.*', str1)
        str1 = pipe.group(1)
    except Exception:
        str1 = str1
    str1 = re.sub(r'^:', '', str1)
    try:
        d = re.match(r'(.*?):(.*)', str1)
        w = d.group(1)
        w = str.lower(w)
        if w in iwlist():
            c = iwlink(w)
            pagename = 'Template:' + d.group(2)
            itw = 't'
        else:
            c = iwlink('zh')
            pagename = 'Template:' + str1
            itw = 'f'
    except Exception:
        c = iwlink('zh')
        pagename = 'Template:' + str1
        itw = 'f'
        w = '.'
    return (await wi(c, w, pagename, itw, ignoremessage='f', template='t'))


if __name__ == '__main__':
    print(asyncio.run(wiki('wiki Netherite')))
