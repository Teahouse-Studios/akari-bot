import re
import traceback

from core.logger import Logger
from core.queue import JobQueue
from core.scheduler import Scheduler, IntervalTrigger
from core.utils.templist import TempList
from modules.wiki import WikiLib
from modules.wikilog.database.models import WikiLogTargetSetInfo
from modules.wikilog.utils import convert_data_to_text

fetch_cache = {}


@Scheduler.scheduled_job(IntervalTrigger(seconds=60))
async def wiki_log():
    fetches = await WikiLogTargetSetInfo.return_all_data()
    matched_logs = {}
    Logger.debug(fetches)
    for id_ in fetches:
        Logger.debug(f"Checking fetch {id_}...")
        if id_ not in fetch_cache:
            fetch_cache[id_] = {}
        if id_ not in matched_logs:
            matched_logs[id_] = {}
        for wiki in fetches[id_]:
            Logger.debug(f"Checking fetch {id_} {wiki}...")
            if wiki not in fetch_cache[id_]:
                fetch_cache[id_][wiki] = {
                    "AbuseLog": TempList(300),
                    "RecentChanges": TempList(300),
                }
            if wiki not in matched_logs[id_]:
                matched_logs[id_][wiki] = {"AbuseLog": [], "RecentChanges": []}
            use_bot = fetches[id_][wiki]["use_bot"]
            query_wiki = WikiLib(wiki)
            await query_wiki.fixup_wiki_info()
            Logger.debug(query_wiki.wiki_info.api)
            if fetches[id_][wiki]["AbuseLog"]["enable"]:
                try:
                    query = await query_wiki.get_json(
                        action="query",
                        list="abuselog",
                        aflprop="user|title|action|result|filter|timestamp",
                        _no_login=not use_bot,
                        afllimit=30,
                    )
                    if "error" not in query:
                        first_fetch = False
                        if not fetch_cache[id_][wiki]["AbuseLog"]:
                            first_fetch = True
                        for y in query["query"]["abuselog"]:
                            identify = convert_data_to_text(y)
                            if identify not in fetch_cache[id_][wiki]["AbuseLog"]:
                                fetch_cache[id_][wiki]["AbuseLog"].append(identify)
                                if not first_fetch:
                                    matched_f = False
                                    if (
                                        "*" in fetches[id_][wiki]["AbuseLog"]["filters"]
                                        or not fetches[id_][wiki]["AbuseLog"]["filters"]
                                    ):
                                        matched_f = True
                                    else:
                                        for f in fetches[id_][wiki]["AbuseLog"][
                                            "filters"
                                        ]:
                                            fc = re.compile(f)
                                            if fc.search(identify):
                                                matched_f = True
                                                break
                                    if matched_f:
                                        matched_logs[id_][wiki]["AbuseLog"].append(y)
                except Exception:
                    Logger.error(traceback.format_exc())
            if fetches[id_][wiki]["RecentChanges"]["enable"]:
                try:
                    query = await query_wiki.get_json(
                        action="query",
                        list="recentchanges",
                        rcprop="title|user|timestamp|loginfo|comment|redirect|flags|sizes|ids",
                        _no_login=not use_bot,
                        rclimit=100,
                        rcshow="|".join(fetches[id_][wiki]["RecentChanges"]["rcshow"]),
                    )
                    if "error" not in query:
                        first_fetch = False
                        if not fetch_cache[id_][wiki]["RecentChanges"]:
                            first_fetch = True
                        for y in query["query"]["recentchanges"]:
                            if "actionhidden" in y:
                                continue
                            identify = convert_data_to_text(y)
                            if identify not in fetch_cache[id_][wiki]["RecentChanges"]:
                                fetch_cache[id_][wiki]["RecentChanges"].append(identify)
                                if not first_fetch:
                                    matched_f = False
                                    if (
                                        "*"
                                        in fetches[id_][wiki]["RecentChanges"][
                                            "filters"
                                        ]
                                        or not fetches[id_][wiki]["RecentChanges"][
                                            "filters"
                                        ]
                                    ):
                                        matched_f = True
                                    else:
                                        for f in fetches[id_][wiki]["RecentChanges"][
                                            "filters"
                                        ]:
                                            fc = re.compile(f)
                                            if fc.search(identify):
                                                matched_f = True
                                                break
                                    if matched_f:
                                        matched_logs[id_][wiki]["RecentChanges"].append(
                                            y
                                        )
                except Exception:
                    Logger.error(traceback.format_exc())
    await JobQueue.trigger_hook_all("wikilog.matched", matched_logs=matched_logs)
