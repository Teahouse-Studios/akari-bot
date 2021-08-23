import asyncio
import json
import traceback

from core.loader.decorator import command
from core.logger import Logger
from core.utils import get_url
from core.elements import FetchTarget
from core.dirty_check import check

from modules.utils.UTC8 import UTC8

from database import BotDBUtil

@command('__check_newbie__', need_superuser=True, autorun=True)
async def newbie(bot: FetchTarget):
    Logger.info('Subbot newbie launched')
    url = 'https://minecraft.fandom.com/zh/api.php?action=query&list=logevents&letype=newusers&format=json'
    while True:
        try:
            file = json.loads(await get_url(url))
            qq = []
            for x in file['query']['logevents'][:]:
                qq.append(x['title'])
            while True:
                c = False
                try:
                    qqqq = json.loads(await get_url(url))
                    for xz in qqqq['query']['logevents'][:]:
                        if xz['title'] in qq:
                            pass
                        else:
                            s = await check(UTC8(xz['timestamp'], 'onlytime') + '新增新人：\n' + xz['title'])
                            if s.find("<吃掉了>") != -1 or s.find("<全部吃掉了>") != -1:
                                s = s + '\n检测到外来信息介入，请前往日志查看所有消息。' \
                                         'https://minecraft.fandom.com/zh/wiki/Special:%E6%97%A5%E5%BF%97?type=newusers'
                            for x in BotDBUtil.Module.get_enabled_this('__check_newbie__'):
                                fetch = await bot.fetch_target(x)
                                await fetch.sendMessage(s)
                            c = True
                except Exception:
                    pass
                if c:
                    break
                else:
                    await asyncio.sleep(10)
            await asyncio.sleep(5)
        except Exception:
            traceback.print_exc()
