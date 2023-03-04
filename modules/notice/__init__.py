from core.builtins import Bot
from core.component import on_command
from .server import server

ntc = on_command('notice', developers='haoye_qwq')

@ntc.handle('<ServerIP> {向启用notice模块的群广播游戏邀请}')
async def notice(msg: Bot.MessageSession):
    get_str = msg.parsed_msg.get('<ServerIP>')
    nickname = msg.target.senderName
    mssg = await server(get_str)
    sstr = f"[由{nickname}发送的游戏邀请]:\n一起来玩Minecraft多人游戏吧！\n{mssg}"
    await Bot.FetchTarget.post_message('notice', sstr)
    await msg.sendMessage(sstr)