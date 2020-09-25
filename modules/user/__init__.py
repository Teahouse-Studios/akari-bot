import re

from modules.help import userhelp
from modules.interwikilist import iwlink, iwlist
from .userlib import User


async def main(command):
    try:
        commandsplit = command.split(' ')
    except Exception:
        commandsplit = []
    if '-h' in commandsplit:
        return userhelp()
    else:
        s = re.match(r'~(.*?) (.*)', command)
        if s:
            metaurl = 'https://' + s.group(1) + '.gamepedia.com/'
            if '-r' in commandsplit:
                rmargv = re.sub(' -r|-r ', '', s.group(2))
                return await User(metaurl, rmargv, '-r')
            elif '-p' in commandsplit:
                rmargv = re.sub(' -p|-p ', '', s.group(2))
                return await User(metaurl, rmargv, '-p')
            else:
                return await User(metaurl, s.group(2))
        i = re.match(r'(.*?):(.*)', command)
        if i:
            w = i.group(1)
            rmargv = i.group(2)
            if w in iwlist():
                metaurl = iwlink(w)
                if '-r' in commandsplit:
                    rmargv = re.sub(' -r|-r ', '', rmargv)
                    return await User(metaurl, rmargv, '-r')
                elif '-p' in commandsplit:
                    rmargv = re.sub(' -p|-p ', '', rmargv)
                    return await User(metaurl,rmargv, '-p')
                else:
                    return await User(metaurl, rmargv)
            else:
                metaurl = 'https://minecraft.gamepedia.com/'
                if '-r' in commandsplit:
                    rmargv = re.sub(' -r|-r ', '', rmargv)
                    return await User(metaurl, rmargv,'-r')
                elif '-p' in commandsplit:
                    rmargv = re.sub(' -p|-p ', '', rmargv)
                    return await User(metaurl,rmargv, '-p')
                else:
                    return await User(metaurl, rmargv)
        else:
            metaurl = 'https://minecraft.gamepedia.com/'
            if '-r' in commandsplit:
                rmargv = re.sub(' -r|-r ', '', command)
                return await User(metaurl, rmargv, '-r')
            elif '-p' in commandsplit:
                rmargv = re.sub(' -p|-p ', '', command)
                return await User(metaurl, rmargv, '-p')
            else:
                return await User(metaurl, command)



command = {'user': 'user'}
