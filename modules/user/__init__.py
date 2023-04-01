import re

from core.builtins import Bot
from core.component import on_command
from modules.wiki.utils.dbutils import WikiTargetInfo
from .user import get_user_info

usr = on_command('user', alias=['u'],
                 developers=['OasisAkari'])


@usr.handle('<username> [-p] {获取一个MediaWiki用户的信息。}', options_desc={'-p': '生成一张图片'})
async def user(msg: Bot.MessageSession):
    target = WikiTargetInfo(msg)
    get_url = target.get_start_wiki()
    if get_url:
        metaurl = get_url
        username = msg.parsed_msg['<username>']
        match_interwiki = re.match(r'(.*?):(.*)', username)
        if match_interwiki:
            interwikis = target.get_interwikis()
            if match_interwiki.group(1) in interwikis:
                return await msg.finish(
                    await get_user_info(interwikis[match_interwiki.group(1)], match_interwiki.group(2),
                                        pic=msg.parsed_msg['-p']))
        await msg.finish(await get_user_info(metaurl, username, pic=msg.parsed_msg['-p']))
    else:
        await msg.finish('未设置起始wiki。')
