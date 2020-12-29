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

wiki = wiki().main

async def main(message, group=0):
    if message == '-h':
        return wikihelp()
    else:
        matchsite = re.match(r'~(.*?) (.*)', message)
        if matchsite:
            wikiurl = 'https://' + matchsite.group(1) + '.gamepedia.com/'
            return await wiki(wikiurl, matchsite.group(2), 'gp:' + matchsite.group(1))
        return await choosemethod(message, group)


async def choosemethod(matchmsg, group=0, basewiki='en'):
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
                elif interwiki in ['Wikipedia', 'wikipedia', 'WP', 'wp']:
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
    z = []
    a = '\n'
    for x in message:
        pipe = re.match(r'(.*?)\|.*', x)
        if pipe:
            x = pipe.group(1)
        x = re.sub(r'^:', '', x)
        url = iwlink('zh')
        pagename = x
        interwiki = ''
        matchinterwiki = re.match(r'(.*?):(.*)', x, re.I)
        if matchinterwiki:
            z.append(await choosemethod(x, basewiki='zh'))
        else:
            z.append(await wiki(url, pagename, interwiki))
    return a.join(z)


async def imarc(message):
    z = []
    a = '\n'
    for x in message:
        pipe = re.match(r'(.*?)\|.*', x, re.I)
        x = pipe.group(1)
        x = re.sub(r'^:', '', x)
        url = 'https://wiki.arcaea.cn/'
        interwiki = ''
        z.append(await wiki(url, x, interwiki, igmessage=True))
    return a.join(z)


async def imt(message):
    z = []
    a = '\n'
    for x in message:
        pipe = re.match(r'(.*?)\|.*', x, re.I)
        if pipe:
            x = pipe.group(1)
        x = re.sub(r'^:', '', x)
        url = iwlink('zh')
        pagename = 'Template:' + x
        matchinterwiki = re.match(r'(.*?):(.*)', x)
        interwiki = ''
        if matchinterwiki:
            interwiki = matchinterwiki.group(1)
            interwiki = str.lower(interwiki)
            if interwiki in iwlist():
                url = iwlink(interwiki)
                pagename = 'Template:' + matchinterwiki.group(2)
            else:
                interwiki = ''
                pagename = 'Template:' + x
        z.append(await wiki(url, pagename, interwiki, igmessage=False, template=True))
    return a.join(z)


command = {'wiki': 'wiki'}
