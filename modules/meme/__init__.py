from core.builtins import Bot
from core.component import module
from core.dirty_check import check
#from modules.meme.jiki import jiki
from modules.meme.moegirl import moegirl
from modules.meme.nbnhhsh import nbnhhsh
from modules.meme.urban import urban

meme = module(
    bind_prefix='meme',
    # well, people still use it though it only lived for an hour or so
    alias=['nbnhhsh'],
    desc='{meme.help.desc}',
    developers=['Dianliang233'])


@meme.handle(help_doc='<term> {{meme.help}}')
async def _(msg: Bot.MessageSession):
#   res_jiki = await jiki(msg.parsed_msg['<term>'])
#   R.I.P. jikipedia
    res_moegirl = await moegirl(msg.parsed_msg['<term>'], msg.locale)
    res_nbnhhsh = await nbnhhsh(msg.parsed_msg['<term>'], msg.locale)
    res_urban = await urban(msg.parsed_msg['<term>'], msg.locale)
    chk = await check(res_moegirl, res_nbnhhsh, res_urban)
    res = ''
    for i in chk:
        if not i['status']:
            i = '[???] <REDACTED>'
            res += i + '\n'
        else:
            res += i['content'] + '\n'
    await msg.finish(res)
