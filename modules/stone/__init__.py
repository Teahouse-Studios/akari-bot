import secrets

from core.builtins import Bot
from core.component import module
from core.petal import gained_petal


stone = module('stone', developers=['OasisAkari'], desc='{stone.help.desc}')

@stone.command()
@stone.regex(r'打水漂')
async def _(msg: Bot.MessageSession):
    count = secrets.randbelow(11)
    if count == 0:
        send = msg.locale.t('stone.message.skip.nothing')
    else:
        send = msg.locale.t('stone.message.skip', count=count)

    if count == 10:
        if g := (g_msg := await gained_petal(msg, 1)):
            send += '\n' + g
    await msg.finish(send)
