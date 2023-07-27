import hashlib

from core.builtins import Bot
from core.component import module

h = module('hash', developers=['Dianliang233'], desc='{hash.help}', )


@h.handle('<algorithm> <string> [<encoding>] {{hash.help}}')
async def _(msg: Bot.MessageSession, algorithm: str, string: str, encoding: str = 'utf-8'):
    try:
        hash_ = hashlib.new(algorithm, string.encode(encoding))
        await msg.finish(msg.locale.t('hash.message.output', algorithm=hash_.name, digest=hash_.hexdigest()))
    except ValueError:
        await msg.finish(f"{msg.locale.t('hash.message.unsupported_algorithm', algorithm=algorithm)}\n"
                         f"{msg.locale.t('hash.message.algorithms_list', algorithms=', '.join(hashlib.algorithms_available))}")


@h.handle('list {{hash.help.list}}')
async def _(msg: Bot.MessageSession):
    await msg.finish(msg.locale.t('hash.message.algorithms_list', algorithms=', '.join(hashlib.algorithms_available)))
