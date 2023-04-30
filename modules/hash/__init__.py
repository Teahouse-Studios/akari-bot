import hashlib

from core.builtins import Bot
from core.component import module

h = module('hash', alias={'rand': 'random', 'rng': 'random'},
           developers=['Dianliang233'], desc='{hash.help.desc}', )


@h.handle('<algorithm> <str> [<encoding>] {{hash.help.generate}}')
async def _(msg: Bot.MessageSession):
    algorithm = msg.parsed_msg['<algorithm>']
    string = msg.parsed_msg['<str>']
    encoding = msg.parsed_msg.get('<encoding>', 'utf-8')
    hash_ = hashlib.new(algorithm, string.encode(encoding))
    await msg.finish(msg.locale.t('hash.output', algorithm=hash_.name, digest=hash_.hexdigest()))


@h.handle('algorithms {{hash.help.algorithms}}')
async def _(msg: Bot.MessageSession):
    await msg.finish(msg.locale.t('hash.algorithms', algorithms=', '.join(hashlib.algorithms_available)))
