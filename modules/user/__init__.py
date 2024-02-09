import re

from core.builtins import Bot
from core.component import module
from modules.wiki.utils.dbutils import WikiTargetInfo
from .user import get_user_info

usr = module('user',
              developers=['OasisAkari'],
              recommend_modules='wiki'
            )


@usr.command('<username> [-r] {{user.help.desc}}',
              options_desc={'-r': '{user.help.option.r}'})
async def user(msg: Bot.MessageSession, username: str, gp_mode = False):
    if msg.parsed_msg.get('-r', False):
        gp_mode = True
    target = WikiTargetInfo(msg)
    get_url = target.get_start_wiki()
    if get_url:
        match_interwiki = re.match(r'(.*?):(.*)', username)
        if match_interwiki:
            interwikis = target.get_interwikis()
            if match_interwiki.group(1) in interwikis:
                await get_user_info(msg, interwikis[match_interwiki.group(1)], match_interwiki.group(2), gp_mode)
        await get_user_info(msg, get_url, username, gp_mode)
    else:
        await msg.finish(msg.locale.t('wiki.message.not_set'))
