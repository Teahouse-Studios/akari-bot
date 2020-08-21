import re

from modules.help import userhelp
from modules.interwikilist import iwlink, iwlist
from .ruserlib import rUser1
from .userlib import User1


async def Username(name):
    name = re.sub(r'^User', 'user', name)
    if name.find(" -h") != -1:
        return userhelp()
    else:
        try:
            q = re.match(r'^user-(.*?) (.*)', name)
            w = q.group(1)
            if w in iwlist():
                url = iwlink(w)
                if name.find(" -r") != -1:
                    x = re.sub(' -r', '', q.group(2))
                    return await rUser1(url, x)
                else:
                    return await User1(url, q.group(2))
            else:
                return '未知语言，请使用~user -h查看帮助。'
        except Exception:
            q = re.match(r'^user (.*)', name)
            try:
                s = re.match(r'~(.*?) (.*)', q.group(1))
                metaurl = 'https://' + s.group(1) + '.gamepedia.com/'
                if name.find(' -r') != -1:
                    x = re.sub(' -r', '', s.group(2))
                    return await rUser1(metaurl, x)
                else:
                    return await User1(metaurl, q.group(2))
            except Exception:
                try:
                    i = re.match(r'(.*?):(.*)', q.group(1))
                    w = i.group(1)
                    x = i.group(2)
                    if w in iwlist():
                        try:
                            metaurl = iwlink(w)
                            if name.find(' -r') != -1:
                                x = re.sub(' -r', '', x)
                                return (await rUser1(metaurl, x))
                            else:
                                return (await User1(metaurl, x))
                        except  Exception as e:
                            return ('发生错误：' + str(e))
                    else:
                        try:
                            metaurl = 'https://minecraft.gamepedia.com/'
                            if name.find(' -r') != -1:
                                x = re.sub(' -r', '', x)
                                return (rUser1(metaurl, x))
                            else:
                                return User1(metaurl, x)
                        except  Exception as e:
                            return ('发生错误：' + str(e))
                except Exception:
                    metaurl = 'https://minecraft.gamepedia.com/'
                    if name.find(" -r") != -1:
                        x = re.sub(' -r', '', q.group(1))
                        return (await rUser1(metaurl, x))
                    else:
                        return await User1(metaurl, q.group(1))
