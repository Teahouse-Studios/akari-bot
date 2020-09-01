import asyncio
import re
import traceback

from modules.help import wikihelp
from modules.interwikilist import iwlist, iwlink
from .wikilib import wiki1, wiki2


async def wiki(message, group=0):
    if message.find(' -h') != -1:
        return wikihelp()
    else:
        lower = re.sub(r'^Wiki', 'wiki', message)
        try:
            matchmsg = re.match(r'^wiki-(.*?) (.*)', lower)
            interwiki = matchmsg.group(1)
            print(interwiki)
            if interwiki in iwlist():
                return await wiki2(matchmsg.group(1), matchmsg.group(2))
            else:
                return '未知语言，请使用~wiki -h查看帮助。'
        except Exception:
            matchmsg = re.match(r'^wiki (.*)', lower)
            try:
                matchsite = re.match(r'~(.*?) (.*)', matchmsg.group(1))
                wikiurl = 'https://' + matchsite.group(1) + '.gamepedia.com/'
                return await wiki1(wikiurl, matchsite.group(2),'gpsitename:'+ matchsite.group(1))
            except Exception:
                try:
                    if group == 250500369 or group == 676942198:
                        pagename = matchmsg.group(1)
                        wikiurl = 'https://wiki.arcaea.cn/'
                        return (await wiki1(wikiurl, pagename, 'arc'))
                    else:
                        matchinterwiki = re.match(r'(.*?):(.*)', matchmsg.group(1))
                        pagename = matchinterwiki.group(2)
                        interwiki = str.lower(matchinterwiki.group(1))
                        if interwiki == 'gpsitename':
                            try:
                                matchsitename = re.match(r'(.*?):(.*)', pagename)
                                wikiurl = 'https://' + matchsitename.group(1) + '.gamepedia.com/'
                                return await wiki1(wikiurl, matchsitename.group(2), 'gpsitename:' + matchsitename.group(1))
                            except  Exception as e:
                                traceback.print_exc()
                                return ('发生错误：' + str(e))
                        if interwiki in iwlist():
                            try:
                                wikiurl = iwlink(interwiki)
                                return (await wiki1(wikiurl, pagename, interwiki))
                            except  Exception as e:
                                traceback.print_exc()
                                return ('发生错误：' + str(e))
                        elif interwiki == 'Wikipedia' or interwiki == 'wikipedia':
                            return ('暂不支持Wikipedia查询。')
                        else:
                            try:
                                wikiurl = 'https://minecraft.gamepedia.com/'
                                return (await wiki1(wikiurl, pagename,''))
                            except  Exception as e:
                                traceback.print_exc()
                                return ('发生错误：' + str(e))
                except Exception:
                    return (await wiki2('en', matchmsg.group(1)))


from .wikitextlib import wi


async def im(message):
    try:
        pipe = re.match(r'(.*?)\|.*', message)
        message = pipe.group(1)
    except Exception:
        pass
    message = re.sub(r'^:', '', message)
    try:
        matchinterwiki = re.match(r'(.*?):(.*)', message)
        interwiki = matchinterwiki.group(1)
        interwiki = str.lower(interwiki)
        pagename = matchinterwiki.group(2)
        if interwiki in iwlist():
            url = iwlink(interwiki)
            itw = True
        elif interwiki == 'gpsitename':
            wikiname = re.match(r'(.*?):(.*)', pagename)
            url = 'https://' + wikiname.group(1) + '.gamepedia.com/'
            pagename = wikiname.group(2)
            interwiki = 'gpsitename:' + wikiname.group(1)
            itw = True
        else:
            url = iwlink('zh')
            pagename = message
            itw = False
    except Exception:
        url = iwlink('zh')
        pagename = message
        itw = False
        interwiki = '.'
    return (await wi(url, interwiki, pagename, itw, ignoremessage=False))


async def imarc(message):
    try:
        pipe = re.match(r'(.*?)\|.*', message)
        message = pipe.group(1)
    except Exception:
        pass
    message = re.sub(r'^:', '', message)
    url = 'https://wiki.arcaea.cn/'
    itw = False
    interwiki = '.'
    return (await wi(url, interwiki, message, itw, ignoremessage=True))


async def imt(message):
    try:
        pipe = re.match(r'(.*?)\|.*', message)
        message = pipe.group(1)
    except Exception:
        pass
    message = re.sub(r'^:', '', message)
    try:
        matchinterwiki = re.match(r'(.*?):(.*)', message)
        interwiki = matchinterwiki.group(1)
        interwiki = str.lower(interwiki)
        if interwiki in iwlist():
            url = iwlink(interwiki)
            pagename = 'Template:' + matchinterwiki.group(2)
            itw = True
        else:
            url = iwlink('zh')
            pagename = 'Template:' + message
            itw = False
    except Exception:
        url = iwlink('zh')
        pagename = 'Template:' + message
        itw = False
        interwiki = '.'
    return (await wi(url, interwiki, pagename, itw, ignoremessage=False, template=True))


if __name__ == '__main__':
    print(asyncio.run(wiki('wiki Netherite')))
