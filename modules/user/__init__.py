import re

from core.builtins import Bot
from core.component import module
from modules.wiki.utils.dbutils import WikiTargetInfo
from .user import get_user_info

usr = module('user', alias='u',
             developers=['OasisAkari'])


@usr.command('<username> [-p] {{user.help.desc}}', options_desc={'-p': '{user.help.option.p}'})
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
                    await get_user_info(msg, interwikis[match_interwiki.group(1)], match_interwiki.group(2),
                                        pic=msg.parsed_msg['-p']))
        await msg.finish(await get_user_info(msg, metaurl, username, pic=msg.parsed_msg['-p']))
    else:
        await msg.finish(msg.locale.t('wiki.message.not_set'))
