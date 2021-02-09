import re

from graia.application import Group, Friend, MessageChain
from graia.application.message.elements.internal import Image, UploadMethods, Plain

from core.template import sendMessage
from modules.wiki.database import get_start_wiki, get_custom_interwiki
from .userlib import GetUser
from modules.wiki.helper import check_wiki_available


# 呜呜呜 想偷个懒都不行
async def main(kwargs: dict):
    command = re.sub('^user ', '', kwargs['trigger_msg'])
    commandsplit = command.split(' ')
    mode = None
    metaurl = None
    username = None
    if Group in kwargs:
        id = kwargs[Group].id
    if Friend in kwargs:
        id = kwargs[Friend].id

    if '-r' in commandsplit:
        mode = '-r'
        commandsplit.remove('-r')
        command = ' '.join(commandsplit)
    if '-p' in commandsplit:
        mode = '-p'
        commandsplit.remove('-p')
        command = ' '.join(commandsplit)
    match_gpsite = re.match(r'~(.*?) (.*)', command)
    if match_gpsite:
        metaurl = f'https://{match_gpsite.group(1)}.gamepedia.com/api.php'
        username = match_gpsite.group(2)
    else:
        match_interwiki = re.match(r'(.*?):(.*)', command)
        if match_interwiki:
            if Group in kwargs:
                table = 'custom_interwiki_group'
            if Friend in kwargs:
                table = 'custon_interwiki_self'
            get_iw = get_custom_interwiki(table, id, match_interwiki.group(1))
            if get_iw:
                metaurl = get_iw
                username = match_interwiki.group(2)
        else:
            if Group in kwargs:
                table = 'start_wiki_link_group'
            if Friend in kwargs:
                table = 'start_wiki_link_self'
            get_url = get_start_wiki(table, id)
            if get_url:
                metaurl = get_url
                username = command
            else:
                await sendMessage(kwargs, '未设置起始Interwiki。')
    result = await GetUser(metaurl, username, mode)
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
help = {'user': {
    'help': '~user [~(wiki_name)] <username> - 获取一个Gamepedia用户的信息。' +
            '\n[-r] - 获取详细信息' +
            '\n[-p] - 生成一张图片'}}
