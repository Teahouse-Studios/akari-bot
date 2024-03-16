from datetime import datetime, timedelta
import traceback

from config import Config
from core.builtins import FormattedTime, I18NContext, MessageSession, Plain, Url
from core.dirty_check import check
from core.logger import Logger
from core.queue import JobQueue
from core.scheduler import Scheduler, DateTrigger
from modules.wiki.utils.dbutils import WikiTargetInfo
from modules.wiki.utils.time import strptime2ts
from modules.wiki.utils.wikilib import WikiLib

# target = WikiTargetInfo()
# wiki = WikiLib(target.get_start_wiki())
wiki = WikiLib('https://youshou.wiki/api.php')


@Scheduler.scheduled_job(DateTrigger(datetime.now()))
async def check_ab():
    try:
        await wiki.fixup_wiki_info()
        pageurl = wiki.wiki_info.articlepath.replace('$1', 'Special:AbuseLog')

        Logger.info('Start abuse monitoring...')
        query = await wiki.get_json(action='query', list='abuselog', aflprop='user|title|action|result|filter|timestamp',
                                    afllimit=30)
        abuses = []
        for x in query["query"]["abuselog"]:
            abuses.append(
                f'{x["user"]}{x["title"]}{x["timestamp"]}{x["filter"]}{x["action"]}{x["result"]}')

        @Scheduler.scheduled_job('interval', seconds=60)
        async def _():
            query2 = await wiki.get_json(action='query', list='abuselog',
                                         aflprop='user|title|action|result|filter|timestamp',
                                         afllimit=30)
            for y in query2["query"]["abuselog"]:
                send_msg = []
                identify = f'{y["user"]}{y["title"]}{y["timestamp"]}{y["filter"]}{y["action"]}{y["result"]}'
                if identify not in abuses:
                    result = y['result']
                    if not result:
                        result = 'pass'
                    s = I18NContext('wiki_rss.message.check_ab.slice',
                                     title=y["title"],
                                     user=y["user"],
                                     time=FormattedTime(strptime2ts(y['timestamp']), date=False, timezone=False).to_dict(),
                                     action=y['action'],
                                     filter_name=y['filter'],
                                     result=result).to_dict()
                                 
                    chk = await check(s)
                    Logger.debug(chk)
                    for z in chk:
                        sz = z['content']
#                        if sz.find("<吃掉了>") != -1 or sz.find("<全部吃掉了>") != -1:
#                            sz = sz.replace("<吃掉了>", I18NContext("check.redacted").to_dict())
#                            sz = sz.replace("<全部吃掉了>", I18NContext("check.redacted.all").to_dict())
                        send_msg.append(sz)
                        if not z['status']:
                            send_msg.append(I18NContext("wiki.message.utils.redacted").to_dict())
                            send_msg.append(Url(pageurl).to_dict())
                        await JobQueue.trigger_hook_all('check_ab', message=send_msg)
                        abuses.append(identify)
    except Exception:
        if Config('debug'):
            Logger.error(traceback.format_exc())


@Scheduler.scheduled_job(DateTrigger(datetime.now()))
async def check_rc():
    try:
        await wiki.fixup_wiki_info()
        pageurl = wiki.wiki_info.articlepath.replace('$1', 'Special:RecentChanges')

        Logger.info('Start recent changes monitoring...')
        query = await wiki.get_json(action='query', list='recentchanges', rcprop='title|user|timestamp', rctype='edit',
                                    rclimit=30)
        changes = []
        for x in query["query"]["recentchanges"]:
            changes.append(f'{x["title"]}{x["user"]}{x["timestamp"]}')

        @Scheduler.scheduled_job('interval', seconds=60)
        async def _():
            query2 = await wiki.get_json(action='query', list='recentchanges',
                                         rcprop='title|user|timestamp', rctype='edit',
                                         rcllimit=30)
            for y in query2["query"]["recentchanges"]:
                send_msg = []
                identify = f'{y["title"]}{y["user"]}{y["timestamp"]}'
                if identify not in changes:
                    s = Plain(f"•{FormattedTime(strptime2ts(y['timestamp']), date=False, timezone=False).to_dict()} - {y['title']} {y['user']}").to_dict()
                    chk = await check(s)
                    Logger.debug(chk)
                    for z in chk:
                        sz = z['content']
#                        if sz.find("<吃掉了>") != -1 or sz.find("<全部吃掉了>") != -1:
#                            sz = sz.replace("<吃掉了>", I18NContext("check.redacted").to_dict())
#                            sz = sz.replace("<全部吃掉了>", I18NContext("check.redacted.all").to_dict())
                        send_msg.append(sz)
                        if not z['status']:
                            send_msg.append(I18NContext("wiki.message.utils.redacted").to_dict())
                            send_msg.append(Url(pageurl).to_dict())
                        await JobQueue.trigger_hook_all('check_rc', message=send_msg)
                        changes.append(identify)
    except Exception:
        if Config('debug'):
            Logger.error(traceback.format_exc())


@Scheduler.scheduled_job(DateTrigger(datetime.now()))
async def check_newbie():
    try:
        Logger.info('Start newbie monitoring...')
        await wiki.fixup_wiki_info()
        pageurl = wiki.wiki_info.articlepath.replace('$1', 'Special:Log?type=newusers')
        query = await wiki.get_json(action='query', list='logevents', letype='newusers')
        newbies = []
        for x in query['query']['logevents']:
            if 'title' in x:
                newbies.append(x['title'])

        @Scheduler.scheduled_job('interval', seconds=60)
        async def _():
            query2 = await wiki.get_json(action='query', list='logevents', letype='newusers')
            for y in query2['query']['logevents']:
                send_msg = []
                if 'title' in y:
                    if y['title'] not in newbies:
                        s = I18NContext('wiki_rss.message.check_newbie.slice',
                                     user=y["title"],
                                     time=FormattedTime(strptime2ts(y['timestamp']), date=False, timezone=False).to_dict()).to_dict()
                        chk = await check(s)
                        Logger.debug(chk)
                        for z in chk:
                            sz = z['content']
#                            if sz.find("<吃掉了>") != -1 or sz.find("<全部吃掉了>") != -1:
#                                sz = sz.replace("<吃掉了>", I18NContext("check.redacted").to_dict())
#                                sz = sz.replace("<全部吃掉了>", I18NContext("check.redacted.all").to_dict())
                            send_msg.append(sz)
                            if not z['status']:
                                send_msg.append(I18NContext("wiki.message.utils.redacted").to_dict())
                                send_msg.append(Url(pageurl).to_dict())
                            await JobQueue.trigger_hook_all('check_newbie', message=send_msg)
    except Exception:
        if Config('debug'):
            Logger.error(traceback.format_exc())