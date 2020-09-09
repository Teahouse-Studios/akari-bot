import asyncio
import re
import traceback

from modules.help import wikihelp
from modules.interwikilist import iwlist, iwlink
from .wikilib import wiki

langcode = ['ab', 'aa', 'af', 'sq', 'am', 'ar', 'hy', 'as', 'ay', 'az', 'ba', 'eu', 'bn', 'dz', 'bh', 'bi', 'br', 'bg',
            'my', 'be', 'km', 'ca', 'zh', 'co', 'hr', 'cs', 'da', 'nl', 'en', 'eo', 'et', 'fo', 'fa', 'fj', 'fi', 'fr',
            'fy', 'gl', 'gd', 'gv', 'ka', 'de', 'el', 'kl', 'gn', 'gu', 'ha', 'he', 'iw', 'hi', 'hu', 'is', 'id', 'in',
            'ia', 'ie', 'iu', 'ik', 'ga', 'it', 'ja', 'jv', 'kn', 'ks', 'kk', 'rw', 'ky', 'rn', 'ko', 'ku', 'lo', 'la',
            'lv', 'li', 'ln', 'lt', 'mk', 'mg', 'ms', 'ml', 'mt', 'mi', 'mr', 'mo', 'mn', 'na', 'ne', 'no', 'oc', 'or',
            'om', 'ps', 'pl', 'pt', 'pa', 'qu', 'rm', 'ro', 'ru', 'sm', 'sg', 'sa', 'sr', 'sh', 'st', 'tn', 'sn', 'sd',
            'si', 'ss', 'sk', 'sl', 'so', 'es', 'su', 'sw', 'sv', 'tl', 'tg', 'ta', 'tt', 'te', 'th', 'to', 'ts', 'tr',
            'tk', 'tw', 'ug', 'uk', 'ur', 'uz', 'vi', 'vo', 'cy', 'wo', 'xh', 'yi', 'yo', 'zu']


async def wmg(message, group=0):
    if message.find(' -h') != -1:
        return wikihelp()
    else:
        lower = re.sub(r'^Wiki', 'wiki', message)
        matchmsg = re.match(r'^wiki-(.*?) (.*)', lower)
        if matchmsg:
            interwiki = matchmsg.group(1)
            if interwiki in iwlist():
                return await wiki(iwlink(interwiki), matchmsg.group(2))
            else:
                return '未知Interwiki，请使用~wiki -h查看帮助。'
        matchmsg = re.match(r'^wiki (.*)', lower)
        if matchmsg:
            matchsite = re.match(r'~(.*?) (.*)', matchmsg.group(1))
            if matchsite:
                wikiurl = 'https://' + matchsite.group(1) + '.gamepedia.com/'
                return await wiki(wikiurl, matchsite.group(2), 'gp:' + matchsite.group(1))
            return await choosemethod(matchmsg.group(1), group)


async def choosemethod(matchmsg, group='0', basewiki='en'):
    try:
        pagename = matchmsg
        if group == 250500369 or group == 676942198:
            wikiurl = 'https://wiki.arcaea.cn/'
            return await wiki(wikiurl, pagename, 'arc')
        else:
            matchinterwiki = re.match(r'(.*?):(.*)', matchmsg)
            if matchinterwiki:
                pagename = matchinterwiki.group(2)
                interwiki = str.lower(matchinterwiki.group(1))
                if interwiki == 'gp':
                    matchsitename = re.match(r'(.*?):(.*)', pagename)
                    wikiurl = 'https://' + matchsitename.group(1) + '.gamepedia.com/'
                    return await wiki(wikiurl, matchsitename.group(2), 'gp:' + matchsitename.group(1))
                if interwiki == 'fd':
                    matchsitename = re.match(r'(.*?):(.*)', pagename)
                    wikiurl = f'https://{matchsitename.group(1)}.fandom.com/'
                    pagename = matchsitename.group(2)
                    interwiki = 'fd:' + matchsitename.group(1)
                    matchlangcode = re.match(r'(.*?):(.*)', matchsitename.group(2))
                    if matchlangcode:
                        if matchlangcode.group(1) in langcode:
                            wikiurl = f'https://{matchsitename.group(1)}.fandom.com/{matchlangcode.group(1)}/'
                            pagename = matchlangcode.group(2)
                            interwiki = 'fd:' + matchsitename.group(1) + ':' + matchlangcode.group(1)
                    return await wiki(wikiurl, pagename, interwiki)
                if interwiki == 'w':
                    matchsitename = re.match(r'(.*?):(.*)', pagename)
                    if matchsitename.group(1) == 'c':
                        matchsitename = re.match(r'(.*?):(.*)', matchsitename.group(2))
                        wikiurl = f'https://{matchsitename.group(1)}.fandom.com/'
                        pagename = matchsitename.group(2)
                        interwiki = 'w:c:' + matchsitename.group(1)
                        matchlangcode = re.match(r'(.*?):(.*)', matchsitename.group(2))
                        if matchlangcode:
                            if matchlangcode.group(1) in langcode:
                                wikiurl = f'https://{matchsitename.group(1)}.fandom.com/{matchlangcode.group(1)}/'
                                pagename = matchlangcode.group(2)
                                interwiki = 'w:c:' + matchsitename.group(1) + ':' + matchlangcode.group(1)
                        return await wiki(wikiurl, pagename, interwiki)
                if interwiki in iwlist():
                    wikiurl = iwlink(interwiki)
                    return await wiki(wikiurl, pagename, interwiki)
                elif interwiki == 'Wikipedia' or interwiki == 'wikipedia':
                    return '暂不支持Wikipedia查询。'
                else:
                    wikiurl = iwlink(basewiki)
                    return await wiki(wikiurl, matchmsg, '')
            else:
                wikiurl = iwlink(basewiki)
                return await wiki(wikiurl, matchmsg, '')
    except Exception as e:
        traceback.print_exc()
        return f'发生错误：{str(e)}'


async def im(message):
    pipe = re.match(r'(.*?)\|.*', message)
    if pipe:
        message = pipe.group(1)
    message = re.sub(r'^:', '', message)
    url = iwlink('zh')
    pagename = message
    interwiki = ''
    matchinterwiki = re.match(r'(.*?):(.*)', message)
    if matchinterwiki:
        return await choosemethod(message, basewiki='zh')
    else:
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
    pipe = re.match(r'(.*?)\|.*', message)
    if pipe:
        message = pipe.group(1)
    message = re.sub(r'^:', '', message)
    matchinterwiki = re.match(r'(.*?):(.*)', message)
    interwiki = matchinterwiki.group(1)
    interwiki = str.lower(interwiki)
    url = iwlink('zh')
    pagename = 'Template:' + message
    if interwiki in iwlist():
        url = iwlink(interwiki)
        pagename = 'Template:' + matchinterwiki.group(2)
    return await wiki(url, pagename, interwiki, igmessage=False, template=True)


if __name__ == '__main__':
    print(asyncio.run(wiki('wiki Netherite')))
