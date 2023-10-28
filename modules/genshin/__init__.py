from core.component import module
from core.builtins import Bot
from enkanetwork import EnkaNetworkAPI
from core.utils.cooldown import CoolDown
from config import Config

genshin = module('genshin', alias='yuanshen', desc='原神角色信息查询。', developers=['ZoruaFox'])

client = EnkaNetworkAPI()

ENKA_URL = Config('enka_url')

@genshin.command()
async def _(msg: Bot.MessageSession):
    data = await client.fetch_user(193588293)
    player_level = {data.player.level}
    await msg.send_message(f'测试用玩家等级：{player_level}')
    
