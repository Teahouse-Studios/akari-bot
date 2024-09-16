import re
from datetime import datetime, timedelta

from core.logger import Logger
from core.queue import JobQueue
from core.scheduler import DateTrigger, Scheduler, CronTrigger, IntervalTrigger
from modules.wiki import WikiLib
from modules.wikilog.dbutils import WikiLogUtil
from core.utils.http import get_url


fetch_cache = {}


@Scheduler.scheduled_job(IntervalTrigger(seconds=60))
async def wiki_log():
    fetches = WikiLogUtil.return_all_data()
    matched_logs = {}
    Logger.debug(fetches)
    for id_ in fetches:
        Logger.debug(f'Checking fetch {id_}...')
        if id_ not in fetch_cache:
            fetch_cache[id_] = {}
        if id_ not in matched_logs:
            matched_logs[id_] = {}
        for wiki in fetches[id_]:
            Logger.debug(f'Checking fetch {id_} {wiki}...')
            first_fetch = False
            if wiki not in fetch_cache[id_]:
                fetch_cache[id_][wiki] = []
                first_fetch = True
            if wiki not in matched_logs[id_]:
                matched_logs[id_][wiki] = {'AbuseLog': [], 'LogEvents': [], 'RecentChanges': []}
            use_bot = fetches[id_][wiki]['use_bot']
            query_wiki = WikiLib(wiki)
            await query_wiki.fixup_wiki_info()
            Logger.debug(query_wiki.wiki_info.api)
            if fetches[id_][wiki]['AbuseLog']['enable']:
                query = await query_wiki.get_json(action='query', list='abuselog',
                                                  aflprop='user|title|action|result|filter|timestamp',
                                                  _no_login=not use_bot,
                                                  afllimit=30)
                if 'error' not in query:
                    for y in query["query"]["abuselog"]:
                        identify = ''
                        if 'title' in y:
                            identify += y['title']
                        if 'user' in y:
                            identify += y['user']
                        if 'timestamp' in y:
                            identify += y['timestamp']
                        if 'filter' in y:
                            identify += y['filter']
                        if 'action' in y:
                            identify += y['action']
                        if 'result' in y:
                            identify += y['result']
                        if identify not in fetch_cache[id_][wiki]:
                            fetch_cache[id_][wiki].append(identify)
                            if not first_fetch:
                                matched_f = False
                                if '*' in fetches[id_][wiki]['AbuseLog']['filters'] or not fetches[id_][wiki]['AbuseLog']['filters']:
                                    matched_f = True
                                else:
                                    for f in fetches[id_][wiki]['AbuseLog']['filters']:
                                        fc = re.compile(f)
                                        if fc.match(identify):
                                            matched_f = True
                                            break
                                if matched_f:
                                    matched_logs[id_][wiki]['AbuseLog'].append(y)

            if fetches[id_][wiki]['RecentChanges']['enable']:
                query = await query_wiki.get_json(action='query', list='recentchanges',
                                                  rcprop='title|user|timestamp|loginfo|comment|redirect|flags|sizes|ids',
                                                  _no_login=not use_bot,
                                                  rclimit=100,
                                                  rcshow='|'.join(fetches[id_][wiki]['RecentChanges']['rcshow']))
                if 'error' not in query:
                    for y in query["query"]["recentchanges"]:
                        if 'actionhidden' in y:
                            continue
                        identify = ''
                        if 'title' in y:
                            identify += y['title']
                        if 'user' in y:
                            identify += y['user']
                        if 'timestamp' in y:
                            identify += y['timestamp']
                        if 'comment' in y:
                            identify += y['comment']
                        if identify not in fetch_cache[id_][wiki]:
                            fetch_cache[id_][wiki].append(identify)
                            if not first_fetch:
                                matched_f = False
                                if '*' in fetches[id_][wiki]['RecentChanges']['filters'] or not fetches[id_][wiki]['RecentChanges']['filters']:
                                    matched_f = True
                                else:
                                    for f in fetches[id_][wiki]['RecentChanges']['filters']:
                                        fc = re.compile(f)
                                        if fc.match(identify):
                                            matched_f = True
                                            break
                                if matched_f:
                                    matched_logs[id_][wiki]['RecentChanges'].append(y)
    await JobQueue.trigger_hook_all('wikilog.matched', matched_logs=matched_logs)
