import os

from core.builtins import Bot
from core.builtins import Image
from core.component import module

arc = module('arcaea', developers=['OasisAkari'], desc='{arcaea.help.desc}',
             alias={'b30': 'arcaea b30', 'a': 'arcaea', 'arc': 'arcaea'})
assets_path = os.path.abspath('./assets/')


@arc.handle()
@arc.handle('<no_one_cares>')
async def _(msg: Bot.MessageSession):
    await msg.finish(Image(assets_path + '/noc.jpg'))
    await msg.finish(Image(assets_path + '/aof.jpg'))
