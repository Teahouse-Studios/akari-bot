from core.builtins import Bot
from core.component import on_command

brc = on_command('broadcast', required_superuser=True, base=True, developers='haoye_qwq')

@brc.handle('<text> {向所有群广播消息}')
async def broadcast(msg: Bot.MessageSession):
    get_str = msg.parsed_msg.get('<text>', False)
    await Bot.FetchTarget.post_message('broadcast', get_str)