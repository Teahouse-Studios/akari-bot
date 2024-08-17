from .modules import *
from .su_utils import *
from core.builtins import Image, Bot
from core.component import on_command
import time

joke = on_command('joke',
                  alias=['arcaea', 'broadcast', 'bugtracker', 'calc', 'chemical_code', 'color', 'convert', 'core',
                         'cytoid', 'dice', 'dictionary''embed_test', 'github', 'hitokoto', 'httpcat', 'idlist', 'info',
                         'maimai', 'mcbbs_news', 'mcplayer', 'mcv', 'mcv_rss', 'minecraft_news', 'mod_dl',
                         'nintendo_err', 'invite', 'ptt', 'random', 'secret', 'server', 'tarot', 'user', 'weekly',
                         'weekly_rss', 'whois', 'wiki', 'zhongli', 'zl', 'zhongli-probe', '_dungeons'], base=True)


@joke.handle('{¿¿¿¿¿}')
async def _(send: Bot.MessageSession):
    msg = await send.sendMessage(
        '¿¿¿¿¿\n今夕事何年~~~~\nhttps://wdf.ink/6Oup\n哼，哼啊啊啊啊啊啊啊啊啊啊啊啊啊啊啊啊啊啊啊\n[它，会在90秒后撤回吗？]')
    time.sleep(90)
    await msg.delete()


@joke.handle('<¿¿¿¿¿> {¿¿¿¿¿}')
async def _(send: Bot.MessageSession):
    msg = await send.sendMessage(
        '¿¿¿¿¿\n今夕事何年~~~~\nhttps://wdf.ink/6Oup\n哼，哼啊啊啊啊啊啊啊啊啊啊啊啊啊啊啊啊啊啊啊\n[它，会在90秒后撤回吗？]')
    time.sleep(90)
    await msg.delete()
