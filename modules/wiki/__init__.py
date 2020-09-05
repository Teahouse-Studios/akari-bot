import asyncio
import re
import traceback

from modules.help import wikihelp
from modules.interwikilist import iwlist, iwlink
from .wikilib import wiki


async def wmg(message, group=0):
    if message.find(' -h') != -1:
        return wikihelp()
    else:
        lower = re.sub(r'^Wiki', 'wiki', message)
        try:
            matchmsg = re.match(r'^wiki-(.*?) (.*)', lower)
            interwiki = matchmsg.group(1)
            print(interwiki)
            if interwiki in iwlist():
                return await wiki(iwlink(interwiki), matchmsg.group(2))
            else:
                return '未知语言，请使用~wiki -h查看帮助。'
        except Exception:
            matchmsg = re.match(r'^wiki (.*)', lower)
            try:
                matchsite = re.match(r'~(.*?) (.*)', matchmsg.group(1))
                wikiurl = 'https://' + matchsite.group(1) + '.gamepedia.com/'
                return await wiki(wikiurl, matchsite.group(2),'gpsitename:'+ matchsite.group(1))
            except Exception:
                try:
                    if group == 250500369 or group == 676942198:
                        pagename = matchmsg.group(1)
                        wikiurl = 'https://wiki.arcaea.cn/'
                        return await wiki(wikiurl, pagename, 'arc')
                    else:
                        matchinterwiki = re.match(r'(.*?):(.*)', matchmsg.group(1))
                        pagename = matchinterwiki.group(2)
                        interwiki = str.lower(matchinterwiki.group(1))
                        if interwiki == 'gpsitename':
                            try:
                                matchsitename = re.match(r'(.*?):(.*)', pagename)
                                wikiurl = 'https://' + matchsitename.group(1) + '.gamepedia.com/'
                                return await wiki(wikiurl, matchsitename.group(2), 'gpsitename:' + matchsitename.group(1))
                            except  Exception as e:
                                traceback.print_exc()
                                return '发生错误：' + str(e)
                        if interwiki in iwlist():
                            try:
                                wikiurl = iwlink(interwiki)
                                return await wiki(wikiurl, pagename, interwiki)
                            except  Exception as e:
                                traceback.print_exc()
                                return '发生错误：' + str(e)
                        elif interwiki == 'Wikipedia' or interwiki == 'wikipedia':
                            return '暂不支持Wikipedia查询。'
                        else:
                            try:
                                wikiurl = 'https://minecraft.gamepedia.com/'
                                return await wiki(wikiurl, pagename, '')
                            except  Exception as e:
                                traceback.print_exc()
                                return '发生错误：' + str(e)
                except Exception:
                    return await wiki('en', matchmsg.group(1))



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
        elif interwiki == 'gpsitename':
            wikiname = re.match(r'(.*?):(.*)', pagename)
            url = 'https://' + wikiname.group(1) + '.gamepedia.com/'
            pagename = wikiname.group(2)
            interwiki = 'gpsitename:' + wikiname.group(1)
        else:
            url = iwlink('zh')
            pagename = message
    except Exception:
        url = iwlink('zh')
        pagename = message
        interwiki = ''
    return await wiki(url, pagename, interwiki)


async def imarc(message):
    try:
        pipe = re.match(r'(.*?)\|.*', message)
        message = pipe.group(1)
    except Exception:
        pass
    message = re.sub(r'^:', '', message)
    url = 'https://wiki.arcaea.cn/'
    interwiki = ''
    return await wiki(url, message, interwiki, igmessage=True)


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
        else:
            url = iwlink('zh')
            pagename = 'Template:' + message
    except Exception:
        url = iwlink('zh')
        pagename = 'Template:' + message
        interwiki = ''
    return await wiki(url, pagename, interwiki, igmessage=False, template=True)


if __name__ == '__main__':
    print(asyncio.run(wiki('wiki Netherite')))
