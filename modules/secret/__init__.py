from datetime import datetime, timedelta

from core.builtins import Bot, Plain
from core.builtins.message.internal import FormattedTime
from core.component import module
from core.dirty_check import check
from core.logger import Logger
from core.scheduler import Scheduler, DateTrigger
from modules.wiki.utils.wikilib import WikiLib
from modules.wiki.utils.time import strptime2ts

wiki = WikiLib('https://zh.minecraft.wiki/api.php')
bot = Bot.FetchTarget
ca = module('__check_abuse__', required_superuser=True, developers=['OasisAkari'])


@ca.handle(DateTrigger(datetime.now() + timedelta(seconds=60)))
async def _():
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
            send_msg = []
            identify = f'{y["user"]}{y["title"]}{y["timestamp"]}{y["filter"]}{y["action"]}{y["result"]}'
            if identify not in abuses:
                s = f'用户：{y["user"]}\n' \
                    f'页面标题：{y["title"]}\n' \
                    f'过滤器名：{y["filter"]}\n' \
                    f'操作：{y["action"]}\n'
                result = y['result']
                if not result:
                    result = 'pass'
                s += '处理结果：' + result

                chk = await check(s)
                Logger.debug(chk)
                for z in chk:
                    sz = z['content']
                    send_msg.append(sz)
                    send_msg.append(FormattedTime(strptime2ts(y['timestamp'])))
                    if not z['status']:
                        send_msg.append('\n检测到外来信息介入，请前往日志查看所有消息。'
                                        'https://zh.minecraft.wiki/w/Special:%E6%BB%A5%E7%94%A8%E6%97%A5%E5%BF%97')
                    await bot.post_message('__check_abuse__', send_msg)
                    abuses.append(identify)


cn = module('__check_newbie__', required_superuser=True, developers=['OasisAkari'])


@cn.handle(DateTrigger(datetime.now() + timedelta(seconds=60)))
async def newbie():
    if bot.name not in ['QQ', 'TEST']:
        return
    Logger.info('Start newbie monitoring...')
    file = await wiki.get_json(action='query', list='logevents', letype='newusers')
    qq = []
    for x in file['query']['logevents']:
        if 'title' in x:
            qq.append(x['title'])

    @Scheduler.scheduled_job('interval', seconds=60)
    async def check_newbie():

        qqqq = await wiki.get_json(action='query', list='logevents', letype='newusers')
        for xz in qqqq['query']['logevents']:
            send_msg = []
            if 'title' in xz:
                if xz['title'] not in qq:
                    send_msg.append(FormattedTime(strptime2ts(xz['timestamp']), date=False, seconds=False))
                    prompt = '新增用户：\n' + xz['title']
                    s = await check(prompt)
                    Logger.debug(s)
                    for z in s:
                        sz = z['content']
                        if not z['status']:
                            sz = sz + '\n检测到外来信息介入，请前往日志查看所有消息。' \
                                      'https://zh.minecraft.wiki/w/Special:%E6%97%A5%E5%BF%97?type=newusers'
                        send_msg.append(Plain(sz))
                        await bot.post_message('__check_newbie__', send_msg)
                        qq.append(xz['title'])
