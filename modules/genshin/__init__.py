import asyncio
from core.component import module
from core.builtins import Bot
from enkanetwork import EnkaNetworkAPI
from core.utils.cooldown import CoolDown
from config import Config
from enkanetwork import Assets


genshin = module('genshin', alias='yuanshen', desc='原神角色信息查询。', developers=['ZoruaFox'])

client = EnkaNetworkAPI()

ENKA_URL = Config('enka_url') #预引入enka节点自定义

@genshin.command()
async def _(msg: Bot.MessageSession):
    data = await client.fetch_user(193588293)
    player_level = {data.player.level}
    await msg.send_message(
        f"测试用玩家昵称：{data.player.nickname}\n"
        f"玩家签名: {data.player.signature}\n"
        f"测试用玩家等级：{data.player.level}\n"
        f"深境螺旋: {data.player.abyss_floor} 层 {data.player.abyss_room} 间"

        )
    
