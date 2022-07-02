import re

from core.component import on_command
from core.elements import Plain, Image
from core.builtins.message import MessageSession
from modules.wiki.dbutils import WikiTargetInfo
from .userlib import GetUser

usr = on_command('user', alias=['u'],
                 developers=['OasisAkari'])


@usr.handle('<username> [-r|-p] {获取一个MediaWiki用户的信息。（-r - 获取详细信息。-p - 生成一张图片。）}')
async def user(msg: MessageSession):
    mode = None
    metaurl = None
    username = None

    if msg.parsed_msg['-r'] is True:
        mode = '-r'
    if msg.parsed_msg['-p'] is True:
        mode = '-p'
    get_url = WikiTargetInfo(msg).get_start_wiki()
    if get_url:
        metaurl = get_url
        username = msg.parsed_msg['<username>']
    else:
        await msg.finish('未设置起始wiki且没有提供Interwiki。')
    match_interwiki = re.match(r'(.*?):(.*)', username)
    if match_interwiki:
        get_iw = WikiTargetInfo(msg).get_interwikis()
        if get_iw and match_interwiki.group(1) in get_iw:
            metaurl = get_iw[match_interwiki.group(1)]
            username = match_interwiki.group(2)
    result = await GetUser(metaurl, username, mode)
    print(result)
    if result:
        matchimg = re.match('(.*)\[\[uimgc:(.*)]]', result)
        if matchimg:
            msgchain = [Plain(matchimg.group(1)), Image(matchimg.group(2))]
        else:
            msgchain = [Plain(result)]
        print(msgchain)
        await msg.finish(msgchain)
