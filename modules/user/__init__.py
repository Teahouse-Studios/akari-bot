import re

from modules.checkuser import checkuser
from modules.help import userhelp
from modules.interwikilist import iwlink, iwlist
from .ruserlib import rUser1
from .userlib import User1


async def main(name):
    x = re.match(r'(?:.*\s?(-.*).*\s)|(?:.*(-.*))', name)
    if x:
        if x.group(1) == '-h' or x.group(2) == '-h':
            return userhelp()
        elif x.group(1) == '-p' or x.group(2) == '-p':
            c = name
            f = re.sub(' -p|-p ', '', c)
            g = re.match(r'^~(.*) (.*)', f)
            if g:
                h = g.group(1)
                h2 = g.group(2)
                h2 = re.sub('_', ' ', h2)
            g = re.match(r'^(.*?) (.*)', f)
            if g:
                h = 'minecraft-' + g.group(1)
                h2 = g.group(2)
                h2 = re.sub('_', ' ', h2)
            g = re.match(r'^(.*?):(.*)', f)
            if g:
                h = 'minecraft-' + g.group(1)
                h2 = g.group(2)
                h2 = re.sub('_', ' ', h2)
            else:
                g = re.match(r'user (.*)', f)
                if g:
                    h = 'minecraft'
                    h2 = g.group(1)
                    h2 = re.sub('_', ' ', h2)
            if checkuser(h, h2):
                h2 = re.sub('User:', '', h2)
                print(h2)
                from .userp import Userp
                return await Userp(h, h2) + "[[usn:" + h2 + "]]"
            else:
                return '没有找到此用户。'
        else:
            s = re.match(r'~(.*?) (.*)', name)
            if s:
                metaurl = 'https://' + s.group(1) + '.gamepedia.com/'
                if x.group(1) == '-r' or x.group(2) == '-r':
                    y = re.sub(' -r|-r ', '', s.group(2))
                    return await rUser1(metaurl, y)
                else:
                    return await User1(metaurl, s.group(2))
            i = re.match(r'(.*?):(.*)', name)
            if i:
                w = i.group(1)
                y = i.group(2)
                if w in iwlist():
                    try:
                        metaurl = iwlink(w)
                        if x.group(1) == '-r' or x.group(2) == '-r':
                            y = re.sub(' -r|-r ', '', y)
                            return await rUser1(metaurl, y)
                        else:
                            return await User1(metaurl, y)
                    except  Exception as e:
                        return ('发生错误：' + str(e))
                else:
                    try:
                        metaurl = 'https://minecraft.gamepedia.com/'
                        if x.group(1) == '-r' or x.group(2) == '-r':
                            y = re.sub(' -r|-r ', '', y)
                            return await rUser1(metaurl, y)
                        else:
                            return await User1(metaurl, y)
                    except  Exception as e:
                        return '发生错误：' + str(e)
            else:
                metaurl = 'https://minecraft.gamepedia.com/'
                if x.group(1) == '-r' or x.group(2) == '-r':
                    y = re.sub(' -r|-r ', '', name)
                    return await rUser1(metaurl, y)
                else:
                    return await User1(metaurl, name)
    else:
        s = re.match(r'~(.*?) (.*)', name)
        if s:
            metaurl = 'https://' + s.group(1) + '.gamepedia.com/'
            return await User1(metaurl, s.group(2))
        i = re.match(r'(.*?):(.*)', name)
        if i:
            w = i.group(1)
            y = i.group(2)
            if w in iwlist():
                try:
                    metaurl = iwlink(w)
                    return await User1(metaurl, y)
                except  Exception as e:
                    return '发生错误：' + str(e)
            else:
                try:
                    metaurl = 'https://minecraft.gamepedia.com/'
                    return await rUser1(metaurl, name)
                except  Exception as e:
                    return '发生错误：' + str(e)
        else:
            metaurl = 'https://minecraft.gamepedia.com/'
            return await User1(metaurl, name)


command = {'user': 'user'}
