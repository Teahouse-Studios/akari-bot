import re

from graia.application import MessageChain
from graia.application.message.elements.internal import Image, Plain

from core.elements.elements import Target
from core.template import sendMessage
from modules_o.wiki.database import WikiDB
from .userlib import GetUser


# 呜呜呜 想偷个懒都不行
async def main(kwargs: dict):
    command = re.sub('^user ', '', kwargs['trigger_msg'])
    commandsplit = command.split(' ')
    mode = None
    metaurl = None
    username = None
    id = kwargs[Target].id

    if '-r' in commandsplit:
        mode = '-r'
        commandsplit.remove('-r')
        command = ' '.join(commandsplit)
    if '-p' in commandsplit:
        mode = '-p'
        commandsplit.remove('-p')
        command = ' '.join(commandsplit)
    table = 'start_wiki_link_' + kwargs[Target].target_from
    get_url = WikiDB.get_start_wiki(table, id)
    if get_url:
        metaurl = get_url
        username = command
    else:
        await sendMessage(kwargs, '未设置起始wiki。')
    match_interwiki = re.match(r'(.*?):(.*)', command)
    if match_interwiki:
        table = 'custom_interwiki_' + kwargs[Target].target_from
        get_iw = WikiDB.get_custom_interwiki(table, id, match_interwiki.group(1))
        if get_iw:
            metaurl = get_iw
            username = match_interwiki.group(2)
    result = await GetUser(metaurl, username, mode)
    if result:
        matchimg = re.match('.*\[\[uimgc:(.*)]]', result)
        if matchimg:
            imgchain = MessageChain.create([Image.fromLocalFile(matchimg.group(1))])
            result = re.sub('\[\[uimgc:.*]]', '', result)
            msgchain = MessageChain.create([Plain(result)])
            msgchain = msgchain.plusWith(imgchain)
        else:
            msgchain = MessageChain.create([Plain(result)])
        await sendMessage(kwargs, msgchain)


command = {'user': main}
alias = {'u': 'user'}
help = {'user': {
    'help': '~user [~(wiki_name)] <username> - 获取一个Gamepedia用户的信息。' +
            '\n[-r] - 获取详细信息' +
            '\n[-p] - 生成一张图片'}}
