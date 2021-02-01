import re

from graia.application import Group, Friend, MessageChain
from graia.application.message.elements.internal import Image, UploadMethods, Plain

from core.template import sendMessage
from modules.wiki.database import get_start_wiki, get_custom_interwiki
from .userlib import User


# 使用次数过少，故简单移植处理（
async def main(kwargs: dict):
    command = re.sub('^user ', '', kwargs['trigger_msg'])
    commandsplit = command.split(' ')
    s = re.match(r'~(.*?) (.*)', command)
    if s:
        metaurl = 'https://' + s.group(1) + '.gamepedia.com/api.php'
        if '-r' in commandsplit:
            rmargv = re.sub(' -r|-r ', '', s.group(2))
            result = await User(metaurl, rmargv, '-r')
        elif '-p' in commandsplit:
            rmargv = re.sub(' -p|-p ', '', s.group(2))
            result = await User(metaurl, rmargv, '-p')
        else:
            result = await User(metaurl, s.group(2))
    i = re.match(r'(.*?):(.*)', command)
    if i:
        w = i.group(1)
        rmargv = i.group(2)
        if Group in kwargs:
            table = 'custom_interwiki_group'
            id = kwargs[Group].id
        if Friend in kwargs:
            table = 'custon_interwiki_self'
            id = kwargs[Friend].id
        get_iw = get_custom_interwiki(table, id, w)
        if get_iw:
            metaurl = get_iw
            if '-r' in commandsplit:
                rmargv = re.sub(' -r|-r ', '', rmargv)
                result = await User(metaurl, rmargv, '-r')
            elif '-p' in commandsplit:
                rmargv = re.sub(' -p|-p ', '', rmargv)
                result = await User(metaurl, rmargv, '-p')
            else:
                result = await User(metaurl, rmargv)
        else:
            if Group in kwargs:
                table = 'start_wiki_link_group'
            if Friend in kwargs:
                table = 'start_wiki_link_self'
            get_url = get_start_wiki(table, id)
            if get_url:
                metaurl = get_url
                if '-r' in commandsplit:
                    rmargv = re.sub(' -r|-r ', '', rmargv)
                    result = await User(metaurl, rmargv, '-r')
                elif '-p' in commandsplit:
                    rmargv = re.sub(' -p|-p ', '', rmargv)
                    result = await User(metaurl, rmargv, '-p')
                else:
                    result = await User(metaurl, rmargv)
    else:
        if Group in kwargs:
            table = 'start_wiki_link_group'
            id = kwargs[Group].id
        if Friend in kwargs:
            table = 'start_wiki_link_self'
            id = kwargs[Friend].id
        get_url = get_start_wiki(table, id)
        if get_url:
            metaurl = get_url
            if '-r' in commandsplit:
                rmargv = re.sub(' -r|-r ', '', command)
                result = await User(metaurl, rmargv, '-r')
            elif '-p' in commandsplit:
                rmargv = re.sub(' -p|-p ', '', command)
                result = await User(metaurl, rmargv, '-p')
            else:
                result = await User(metaurl, command)
    if result:
        matchimg = re.match('.*\[\[uimgc:(.*)]]', result)
        if matchimg:
            if Group in kwargs:
                mth = UploadMethods.Group
            if Friend in kwargs:
                mth = UploadMethods.Friend
            imgchain = MessageChain.create([Image.fromLocalFile(matchimg.group(1), method=mth)])
            result = re.sub('\[\[uimgc:.*]]', '', result)
            msgchain = MessageChain.create([Plain(result)])
            msgchain = msgchain.plusWith(imgchain)
        else:
            msgchain = MessageChain.create([Plain(result)])
        await sendMessage(kwargs, msgchain)


command = {'user': main}
help = {'user':{'module':'获取一个Gamepedia用户的信息。',
                'help':'~user [~(wiki_name)] <username> - 获取一个Gamepedia用户的信息。' +
                       '\n[-r] - 获取详细信息' +
                       '\n[-p] - 生成一张图片'}}
