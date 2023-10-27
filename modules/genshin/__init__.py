from core.component import module
from core.builtins import Bot
from enkapy import Enka
from core.utils.cooldown import CoolDown

genshin = module('genshin', alias='yuanshen', desc='原神角色信息查询。', developers=['ZoruaFox'])

client = Enka()

@genshin.command('<genshin> [<yuanshen>] {{genshin.help}}',
              options_desc={
                  'test': 'Just for test',
              })
async def _(msg: Bot.MessageSession, genshin):
    await msg.finish(client.fetch_user(193588293))
