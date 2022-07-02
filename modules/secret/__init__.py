from core.component import on_startup
from core.dirty_check import check
from core.elements import FetchTarget
from core.logger import Logger
from core.scheduler import Scheduler
from modules.wiki.utils.UTC8 import UTC8
from modules.wiki.wikilib import WikiLib

wiki = WikiLib('https://minecraft.fandom.com/zh/api.php')


@on_startup('__check_newbie__', required_superuser=True, developers=['OasisAkari'])
async def newbie(bot: FetchTarget):
    if bot.name not in ['QQ', 'TEST']:
        return
    Logger.info('Start newbie monitoring...')
    file = await wiki.get_json(action='query', list='logevents', letype='newusers')
    qq = []
    for x in file['query']['logevents'][:]:
        qq.append(x['title'])

    @Scheduler.scheduled_job('interval', seconds=60)
    async def check_newbie():
        qqqq = await wiki.get_json(action='query', list='logevents', letype='newusers')
        for xz in qqqq['query']['logevents'][:]:
            if xz['title'] not in qq:
                prompt = UTC8(xz['timestamp'], 'onlytime') + \
                    '新增新人：\n' + xz['title']
                s = await check(prompt)
                Logger.info(s)
                for z in s:
                    sz = z['content']
                    if not z['status']:
                        sz = sz + '\n检测到外来信息介入，请前往日志查看所有消息。' \
                                  'https://minecraft.fandom.com/zh/wiki/Special:%E6%97%A5%E5%BF%97?type=newusers'
                    await bot.post_message('__check_newbie__', sz)
                    qq.append(xz['title'])


@on_startup('__check_abuse__', required_superuser=True, developers=['OasisAkari'])
async def _(bot: FetchTarget):
    if bot.name not in ['QQ', 'TEST']:
        return
    Logger.info('Start abuse monitoring...')
    query = await wiki.get_json(action='query', list='abuselog', aflprop='user|title|action|result|filter|timestamp',
                                afllimit=30)
    abuses = []
    for x in query["query"]["abuselog"]:
        abuses.append(
            f'{x["user"]}{x["title"]}{x["timestamp"]}{x["filter"]}{x["action"]}{x["result"]}')

    @Scheduler.scheduled_job('interval', seconds=60)
    async def check_abuse():
        query2 = await wiki.get_json(action='query', list='abuselog',
                                     aflprop='user|title|action|result|filter|timestamp',
                                     afllimit=30)
        for y in query2["query"]["abuselog"]:
            identify = f'{y["user"]}{y["title"]}{y["timestamp"]}{y["filter"]}{y["action"]}{y["result"]}'
            if identify not in abuses:
                s = f'用户：{y["user"]}\n' \
                    f'页面标题：{y["title"]}\n' \
                    f'过滤器名：{y["filter"]}\n' \
                    f'操作：{y["action"]}\n'
                result = y['result']
                if result == '':
                    result = 'pass'
                s += '处理结果：' + result + '\n'
                s += UTC8(y['timestamp'], 'full')
                chk = await check(s)
                Logger.info(chk)
                for z in chk:
                    sz = z['content']
                    if not z['status']:
                        sz = sz + '\n检测到外来信息介入，请前往日志查看所有消息。' \
                                  'https://minecraft.fandom.com/zh/wiki/Special:%E6%BB%A5%E7%94%A8%E6%97%A5%E5%BF%97'
                    await bot.post_message('__check_abuse__', sz)
                    abuses.append(identify)
