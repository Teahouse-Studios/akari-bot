import ujson as json

from core.component import on_startup
from core.dirty_check import check
from core.elements import FetchTarget
from core.logger import Logger
from core.scheduler import Scheduler
from core.utils import get_url
from modules.wiki.utils.UTC8 import UTC8


@on_startup('__check_newbie__', required_superuser=True, developers=['OasisAkari'])
async def newbie(bot: FetchTarget):
    Logger.info('Subbot newbie launched')
    url = 'https://minecraft.fandom.com/zh/api.php?action=query&list=logevents&letype=newusers&format=json'
    file = json.loads(await get_url(url))
    qq = []
    for x in file['query']['logevents'][:]:
        qq.append(x['title'])

    @Scheduler.scheduled_job('interval', seconds=60)
    async def check_newbie():
        qqqq = json.loads(await get_url(url))
        for xz in qqqq['query']['logevents'][:]:
            if xz['title'] not in qq:
                prompt = UTC8(xz['timestamp'], 'onlytime') + '新增新人：\n' + xz['title']
                s = await check(prompt)
                Logger.info(s)
                for z in s:
                    s = z['content']
                    if not z['status']:
                        s = s + '\n检测到外来信息介入，请前往日志查看所有消息。' \
                                'https://minecraft.fandom.com/zh/wiki/Special:%E6%97%A5%E5%BF%97?type=newusers'
                    await bot.post_message('__check_newbie__', s)
                    qq.append(xz['title'])
