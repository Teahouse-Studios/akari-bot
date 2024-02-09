from core.builtins import Bot
from core.component import module
from core.dirty_check import check
# from modules.meme.jiki import jiki
from modules.meme.moegirl import moegirl
from modules.meme.nbnhhsh import nbnhhsh
from modules.meme.urban import urban

meme = module(
    bind_prefix='meme',
    # well, people still use it though it only lived for an hour or so
    alias='nbnhhsh',
    desc='{meme.help.desc}',
    developers=['Dianliang233'],
    support_languages=['zh_cn', 'en_us'])


@meme.command('<term> {{meme.help}}')
async def _(msg: Bot.MessageSession, term: str):
    #   res_jiki = await jiki(msg.parsed_msg['<term>'], msg.locale)
    #   R.I.P. jikipedia
    res_moegirl = await moegirl(term, msg.locale)
    res_nbnhhsh = await nbnhhsh(term, msg.locale)
    res_urban = await urban(term, msg.locale)
    chk = await check(res_moegirl, res_nbnhhsh, res_urban)
    res = ''
    for i in chk:
        res += i['content'] + '\n'
    res = res.replace("<吃掉了>", msg.locale.t("check.redacted"))
    res = res.replace("<全部吃掉了>", msg.locale.t("check.redacted.all"))
    await msg.finish(res.strip())
