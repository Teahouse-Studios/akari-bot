from core.builtins import Bot
from core.component import module

brc = module('broadcast', required_superuser=True, developers='haoye_qwq')

@brc.handle('<text> {向所有群广播消息}')
async def broadcast(msg: Bot.MessageSession):
    name = msg.target.senderName
    id = msg.target.senderId
    get_str = msg.parsed_msg.get('<text>', False)
    string_s = f"[由 {name}({id}) 发送的广播]\n{get_str}"
    await Bot.FetchTarget.post_message('broadcast', string_s)
