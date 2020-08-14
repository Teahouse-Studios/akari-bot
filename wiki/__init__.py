import asyncio
import re
import traceback

from help import wikihelp
from interwikilist import iwlist, iwlink
from .wikilib import wiki1, wiki2


async def wiki(message, group=0):
    if message.find(' -h') != -1:
        return (await wikihelp())
    else:
        lower = re.sub(r'^Wiki', 'wiki', message)
        try:
            matchmsg = re.match(r'^wiki-(.*?) (.*)', lower)
            interwiki = matchmsg.group(1)
            print(interwiki)
            if interwiki in iwlist():
                return (await wiki2(matchmsg.group(1), matchmsg.group(2)))
            else:
                return ('未知语言，请使用~wiki -h查看帮助。')
        except:
            matchmsg = re.match(r'^wiki (.*)', lower)
            try:
                matchsite = re.match(r'~(.*?) (.*)', matchmsg.group(1))
                wikiurl = 'https://' + matchsite.group(1) + '.gamepedia.com'
                return (await wiki1(wikiurl, matchsite.group(2)))
            except:
                try:
                    if group == 250500369 or group == 676942198:
                        pagename = matchmsg.group(1)
                        wikiurl = 'https://wiki.arcaea.cn/'
                        return (await wiki1(wikiurl, pagename))
                    else:
                        matchinterwiki = re.match(r'(.*?):(.*)', matchmsg.group(1))
                        pagename = matchinterwiki.group(2)
                        interwiki = str.lower(matchinterwiki.group(1))
                        if interwiki in iwlist():
                            try:
                                wikiurl = iwlink(interwiki)
                                return (await wiki1(wikiurl, pagename))
                            except  Exception as e:
                                traceback.print_exc()
                                return ('发生错误：' + str(e))
                        elif interwiki == 'Wikipedia' or interwiki == 'wikipedia':
                            return ('暂不支持Wikipedia查询。')
                        else:
                            try:
                                wikiurl = 'https://minecraft.gamepedia.com/'
                                return (await wiki1(wikiurl, pagename))
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
        if interwiki in iwlist():
            url = iwlink(interwiki)
            pagename = matchinterwiki.group(2)
            itw = 't'
        else:
            url = iwlink('zh')
            pagename = message
            itw = 'f'
    except Exception:
        url = iwlink('zh')
        pagename = message
        itw = 'f'
        interwiki = '.'
    return (await wi(url, interwiki, pagename, itw, ignoremessage='f'))


async def imarc(message):
    try:
        pipe = re.match(r'(.*?)\|.*', message)
        message = pipe.group(1)
    except Exception:
        pass
    message = re.sub(r'^:', '', message)
    url = 'https://wiki.arcaea.cn/'
    itw = 'f'
    interwiki = '.'
    return (await wi(url, interwiki, message, itw, ignoremessage='t'))


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
            itw = 't'
        else:
            url = iwlink('zh')
            pagename = 'Template:' + message
            itw = 'f'
    except Exception:
        url = iwlink('zh')
        pagename = 'Template:' + message
        itw = 'f'
        interwiki = '.'
    return (await wi(url, interwiki, pagename, itw, ignoremessage='f', template='t'))


if __name__ == '__main__':
    print(asyncio.run(wiki('wiki Netherite')))
