import asyncio
from core.component import module
from core.builtins import Bot
from enkanetwork import EnkaNetworkAPI
from core.utils.cooldown import CoolDown
from config import Config
from enkanetwork import Assets


genshin = module('genshin', alias='yuanshen', desc='原神角色信息查询。', developers=['ZoruaFox'])

client = EnkaNetworkAPI()

ENKA_URL = Config('enka_url') #预引入enka节点在config自定义

@genshin.handle('uid <number> {{genshin.help.uid}}')
async def _(msg: Bot.MessageSession):
    data = await client.fetch_user(msg.parsed_msg['<number>'])
    player_level = {data.player.level}
    await msg.send_message(
        f"玩家昵称：{data.player.nickname}\n"
        f"玩家签名: {data.player.signature}\n"
        f"玩家等级：{data.player.level}\n"
        f"深境螺旋: {data.player.abyss_floor} 层 {data.player.abyss_room} 间\n"
        f"缓存过期时间：{data.ttl} s"
        )
