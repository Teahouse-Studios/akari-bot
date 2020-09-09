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
                return await wiki(wikiurl, matchsite.group(2), 'gp:' + matchsite.group(1))
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
                        if interwiki == 'gp':
                            try:
                                matchsitename = re.match(r'(.*?):(.*)', pagename)
                                wikiurl = 'https://' + matchsitename.group(1) + '.gamepedia.com/'
                                return await wiki(wikiurl, matchsitename.group(2), 'gp:' + matchsitename.group(1))
                            except  Exception as e:
                                traceback.print_exc()
                                return '发生错误：' + str(e)
                        if interwiki == 'fd':
                            try:
                                matchsitename = re.match(r'(.*?):(.*)', pagename)
                                try:
                                    matchlangcode = re.match(r'(.*?):(.*)', matchsitename.group(2))
                                    if matchlangcode.group(1) in langcode:
                                        wikiurl = f'https://{matchsitename.group(1)}.fandom.com/{matchlangcode.group(1)}/'
                                        pagename = matchlangcode.group(2)
                                        interwiki = 'fd:' + matchlangcode.group(1)
                                    else:
                                        wikiurl = f'https://{matchsitename.group(1)}.fandom.com/'
                                        pagename = matchsitename.group(2)
                                        interwiki = 'fd'
                                except Exception:
                                    wikiurl = f'https://{matchsitename.group(1)}.fandom.com/'
                                    pagename = matchsitename.group(2)
                                    interwiki = 'fd'
                                return await wiki(wikiurl, pagename, interwiki)
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
        elif interwiki == 'gp':
            wikiname = re.match(r'(.*?):(.*)', pagename)
            url = 'https://' + wikiname.group(1) + '.gamepedia.com/'
            pagename = wikiname.group(2)
            interwiki = 'gp:' + wikiname.group(1)
        elif interwiki == 'fd':
                matchsitename = re.match(r'(.*?):(.*)', pagename)
                try:
                    matchlangcode = re.match(r'(.*?):(.*)', matchsitename.group(2))
                    if matchlangcode.group(1) in langcode:
                        url = f'https://{matchsitename.group(1)}.fandom.com/{matchlangcode.group(1)}/'
                        pagename = matchlangcode.group(2)
                        interwiki = 'fd:' + matchlangcode.group(1)
                    else:
                        url = f'https://{matchsitename.group(1)}.fandom.com/'
                        pagename = matchsitename.group(2)
                        interwiki = 'fd'
                except Exception:
                    url = f'https://{matchsitename.group(1)}.fandom.com/'
                    pagename = matchsitename.group(2)
                    interwiki = 'fd:'
        else:
            url = iwlink('zh')
            pagename = message
            interwiki = ''
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
