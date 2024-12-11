from core.builtins import Bot
from core.component import module
from .server import server

ntc = module('invite', alias='invi', developers='haoye_qwq')


@ntc.handle('<ServerIP> {向启用invite模块的群广播游戏邀请}')
async def notice(msg: Bot.MessageSession):
    get_str = msg.parsed_msg.get('<ServerIP>')
    nickname = msg.target.sender_name
    mssg = await server(get_str)
    sstr = f"[由{nickname}发送的游戏邀请]:\n一起来玩Minecraft多人游戏吧！\n{mssg}"
    await Bot.FetchTarget.post_message('invite', sstr)
    await msg.sendMessage('已完成发送,请等待响应')
