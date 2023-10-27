from core.component import module
from core.builtins import Bot
from enkapy import Enka
from core.utils.cooldown import CoolDown

genshin = module('genshin', alias='yuanshen', desc='原神角色信息查询。', developers=['ZoruaFox'])

client = Enka()

@genshin.command('test <UID> 只是测试，什么都没有',
                 'placeholder <ph> Placeholder',
)
async def _(msg: Bot.MessageSession, genshin):
    user = await client.fetch_user(193588293)
    player_level = {user.player.level}
    await msg.send_message(player_level)
    
