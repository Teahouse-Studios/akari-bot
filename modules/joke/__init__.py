from .modules import *
from .su_utils import *
from core.builtins import Image, Bot
from core.component import on_command

joke = on_command('joke',  lias=['arcaea', 'broadcast', 'bugtracker', 'calc', 'chemical_code', 'color', 'convert', 'core', 'cytoid', 'dice', 'dictionary''embed_test', 'github', 'hitokoto', 'httpcat', 'idlist', 'info', 'maimai', 'mcbbs_news', 'mcplayer', 'mcv', 'mcv_rss', 'minecraft_news', 'mod_dl', 'nintendo_err', 'notice', 'ptt', 'random', 'secret', 'server', 'tarot', 'user', 'weekly', 'weekly_rss', 'whois', 'wiki', 'zhongli', 'zl',  'zhongli-probe',  '_dungeons'])

@joke.handle('{¿¿¿¿¿}')
async def _(send:Bot.MessageSession):
    await send.sendMessage('¿¿¿¿¿\n今夕事何年~~~~\nhttps://wdf.ink/6Oup\n哼，哼啊啊啊啊啊啊啊啊啊啊啊啊啊啊啊啊啊啊啊')
@joke.handle('<¿¿¿¿¿> {¿¿¿¿¿}')
async def _(send:Bot.MessageSession):
    await send.sendMessage('¿¿¿¿¿\n今夕事何年~~~~\nhttps://wdf.ink/6Oup\n哼，哼啊啊啊啊啊啊啊啊啊啊啊啊啊啊啊啊啊啊啊')