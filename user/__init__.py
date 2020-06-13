import re
from .user import User1
from .ruserlib import rUser1
async def Username(name):
    name = re.sub(r'^User', 'user', name)
    if name.find(" -h")!= -1:
        return ('''~user ~<site> <pagename> - 从指定Gamepedia站点中输出用户信息。
~user <lang>:<pagename>, ~user-<lang> <pagename> - 从指定语言中的Minecraft Wiki中输出用户信息。
~user <pagename> - 从Minecraft Wiki（英文）中输出用户信息。
[-r] - 输出详细信息。
[-p] - 输出一张用户信息的图片（不包含用户组）。''')
    elif name.find(" -r")!=-1:
        m = re.sub(r' -r', '', name)
        try:
            q = re.match(r'^user-(.*) (.*)', m)
            url = 'https://minecraft-' + q.group(1) + '.gamepedia.com'
            w = q.group(1)
            if (w == "cs" or w == "de" or w == "el" or w == "en" or w == "es" or w == "fr" or w == "hu" or w == "it" or w == "ja" or w == "ko" or w == "nl" or w == "pl" or w == "pt" or w == "ru" or w == "th" or w == "tr" or w == "uk" or w == "zh"):
                return (rUser1(url, q.group(2)))
            else:
                return('未知语言，请使用~user -h查看帮助。')
        except:
            q = re.match(r'^user (.*)', m)
            try:
                s = re.match(r'~(.*) (.*)', q.group(1))
                metaurl = 'https://' + s.group(1) + '.gamepedia.com'
                return (rUser1(metaurl, s.group(2)))
            except:
                try:
                    d = re.sub(r':.*', '', q.group(1))
                    x = re.sub(r'^' + d + ':', '', q.group(1))
                    w = d
                    if (w == "cs" or w == "de" or w == "el" or w == "en" or w == "es" or w == "fr" or w == "hu" or w == "it" or w == "ja" or w == "ko" or w == "nl" or w == "pl" or w == "pt" or w == "ru" or w == "th" or w == "tr" or w == "uk" or w == "zh"):
                        try:
                            metaurl = 'https://minecraft-' + w + '.gamepedia.com'
                            return (rUser1(metaurl, x))
                        except  Exception as e:
                            return ('发生错误：' + str(e))
                    else:
                        try:
                            metaurl = 'https://minecraft.gamepedia.com'
                            return (rUser1(metaurl, x))
                        except  Exception as e:
                            return ('发生错误：' + str(e))
                except Exception:
                    metaurl = 'https://minecraft.gamepedia.com'
                    return (rUser1(metaurl, q.group(1)))
    else:
        try:
            q = re.match(r'^user-(.*) (.*)', name)
            url = 'https://minecraft-' + q.group(1) + '.gamepedia.com'
            w = q.group(1)
            if (w == "cs" or w == "de" or w == "el" or w == "en" or w == "es" or w == "fr" or w == "hu" or w == "it" or w == "ja" or w == "ko" or w == "nl" or w == "pl" or w == "pt" or w == "ru" or w == "th" or w == "tr" or w == "uk" or w == "zh"):
                return (User1(url, q.group(2)))
            else:
                return('未知语言，请使用~user -h查看帮助。')
        except:
            q = re.match(r'^user (.*)', name)
            try:
                s = re.match(r'~(.*) (.*)', q.group(1))
                metaurl = 'https://' + s.group(1) + '.gamepedia.com'
                return (User1(metaurl, s.group(2)))
            except:
                try:
                    d = re.sub(r':.*', '', q.group(1))
                    x = re.sub(r'^' + d + ':', '', q.group(1))
                    w = d
                    if (w == "cs" or w == "de" or w == "el" or w == "en" or w == "es" or w == "fr" or w == "hu" or w == "it" or w == "ja" or w == "ko" or w == "nl" or w == "pl" or w == "pt" or w == "ru" or w == "th" or w == "tr" or w == "uk" or w == "zh"):
                        try:
                            metaurl = 'https://minecraft-' + w + '.gamepedia.com'
                            return (User1(metaurl, x))
                        except  Exception as e:
                            return ('发生错误：' + str(e))
                    else:
                        try:
                            metaurl = 'https://minecraft.gamepedia.com'
                            return (User1(metaurl, x))
                        except  Exception as e:
                            return ('发生错误：' + str(e))
                except Exception:
                    metaurl = 'https://minecraft.gamepedia.com'
                    return (User1(metaurl, q.group(1)))

