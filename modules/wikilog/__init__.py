import re
from collections import deque

import orjson

from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext
from core.builtins.session.internal import FetchedMessageSession
from core.component import module
from core.config import Config
from core.constants.default import wiki_whitelist_url_default
from core.logger import Logger
from core.scheduler import IntervalTrigger
from modules.wiki.utils.ab import convert_ab_to_detailed_format
from modules.wiki.utils.rc import convert_rc_to_detailed_format
from modules.wiki.utils.wikilib import WikiLib
from .database.models import WikiLogTargetSetInfo
from .utils import convert_data_to_text

wiki_whitelist_url = Config("wiki_whitelist_url", wiki_whitelist_url_default, table_name="module_wiki")

type_map = {
    "abuselog": "AbuseLog",
    "recentchanges": "RecentChanges",
    "AbuseLog": "AbuseLog",
    "RecentChanges": "RecentChanges",
    "ab": "AbuseLog",
    "rc": "RecentChanges",
}

rcshows = [
    "!anon",
    "!autopatrolled",
    "!bot",
    "!minor",
    "!patrolled",
    "!redirect",
    "anon",
    "autopatrolled",
    "bot",
    "minor",
    "patrolled",
    "redirect",
    "unpatrolled",
]

wikilog = module(
    "wikilog", developers=["OasisAkari"], required_admin=True, doc=True, rss=True, required_superuser=True
)


@wikilog.command(
    "add wiki <apilink> {{I18N:wikilog.help.add.wiki}}",
    "reset wiki <apilink> {{I18N:wikilog.help.reset.wiki}}",
    "remove wiki <apilink> {{I18N:wikilog.help.remove.wiki}}",
)
async def _(msg: Bot.MessageSession, apilink: str):
    wiki_info = WikiLib(apilink)
    status = await wiki_info.check_wiki_available()
    in_allowlist = True
    wiki_name = status.value.name
    if status.value.lang:
        wiki_name += f" ({status.value.lang})"
    if Bot.Info.use_url_manager:
        in_allowlist = status.value.in_allowlist
        if status.value.in_blocklist and not in_allowlist:
            await msg.finish(
                I18NContext("wiki.message.invalid.blocked", name=wiki_name)
            )
    if not in_allowlist:
        prompt = [I18NContext("wikilog.message.untrust.wiki", name=wiki_name)]
        if wiki_whitelist_url:
            prompt.append(I18NContext("wiki.message.wiki_audit.untrust.address", url=wiki_whitelist_url))
        await msg.finish(prompt)
    if status.available:
        records = await WikiLogTargetSetInfo.get_by_target_id(msg)
        await records.conf_wiki(
            status.value.api,
            add="add" in msg.parsed_msg,
            reset="reset" in msg.parsed_msg,
        )
        await msg.finish(
            I18NContext("wikilog.message.config.wiki.success", wiki=wiki_name)
        )
    else:
        await msg.finish(
            I18NContext("wikilog.message.config.wiki.failed", message=status.message)
        )


@wikilog.command(
    "enable <apilink> <logtype> {{I18N:wikilog.help.enable.logtype}}",
    "disable <apilink> <logtype> {{I18N:wikilog.help.disable.logtype}}",
)
async def _(msg: Bot.MessageSession, apilink, logtype: str):
    logtype = type_map.get(logtype)
    if logtype:
        wiki_info = WikiLib(apilink)
        status = await wiki_info.check_wiki_available()
        if status.available:
            wiki_name = status.value.name
            if status.value.lang:
                wiki_name += f" ({status.value.lang})"
            records = await WikiLogTargetSetInfo.get_by_target_id(msg)
            if await records.conf_log(
                status.value.api, logtype, enable="enable" in msg.parsed_msg
            ):
                await msg.finish(
                    I18NContext(
                        "wikilog.message.enable.log.success",
                        wiki=wiki_name,
                        logtype=logtype,
                    )
                )
            else:
                await msg.finish(
                    I18NContext(
                        "wikilog.message.enable.log.failed",
                        apilink=apilink,
                        logtype=logtype,
                    )
                )
        else:
            await msg.finish(
                I18NContext(
                    "wikilog.message.enable.log.failed",
                    apilink=apilink,
                    logtype=logtype,
                )
            )
    else:
        await msg.finish(
            I18NContext("wikilog.message.enable.log.invalid_logtype", logtype=logtype)
        )


@wikilog.command("filter test <filters> <example> {{I18N:wikilog.help.filter.test}}")
async def _(msg: Bot.MessageSession, filters: str, example: str):
    f = re.compile(filters)
    if m := f.search(example):
        await msg.finish(
            I18NContext(
                "wikilog.message.filter.test.success",
                start=m.start(),
                end=m.end(),
                string=example[m.start(): m.end()],
            )
        )
    else:
        await msg.finish(I18NContext("wikilog.message.filter.test.failed"))


@wikilog.command("filter example <example> {{I18N:wikilog.help.filter.example}}")
async def _(msg: Bot.MessageSession):
    try:
        example = msg.trigger_msg.replace("wikilog filter example ", "", 1)
        Logger.debug(example)
        load = orjson.loads(example)
        await msg.send_message(convert_data_to_text(load))
    except Exception:
        await msg.send_message(I18NContext("wikilog.message.filter.example.invalid"))


@wikilog.command("api get <apilink> <logtype> {{I18N:wikilog.help.api.get}}")
async def _(msg: Bot.MessageSession, apilink, logtype):
    records = await WikiLogTargetSetInfo.get_by_target_id(msg)
    infos = records.infos
    wiki_info = WikiLib(apilink)
    status = await wiki_info.check_wiki_available()
    logtype = type_map.get(logtype)
    if status.available:
        if status.value.api in infos:
            if logtype == "RecentChanges":
                await msg.finish(
                    await wiki_info.return_api(
                        _no_format=True,
                        action="query",
                        list="recentchanges",
                        rcprop="title|user|timestamp|loginfo|comment|redirect|flags|sizes|ids",
                        rclimit=100,
                        rcshow="|".join(
                            infos[status.value.api]["RecentChanges"]["rcshow"]
                        ),
                    )
                )
            if logtype == "AbuseLog":
                await msg.finish(
                    await wiki_info.return_api(
                        _no_format=True,
                        action="query",
                        list="abuselog",
                        aflprop="user|title|action|result|filter|timestamp",
                        afllimit=30,
                    )
                )
        else:
            await msg.finish(I18NContext("wikilog.message.filter.set.failed"))
    else:
        await msg.finish(
            I18NContext(
                "wikilog.message.enable.log.failed", apilink=apilink, logtype=logtype
            )
        )


@wikilog.command("filter set <apilink> <logtype> ... {{I18N:wikilog.help.filter.set}}")
@wikilog.command("filter reset <apilink> <logtype> {{I18N:wikilog.help.filter.reset}}")
async def _(msg: Bot.MessageSession, apilink: str, logtype: str):
    if "reset" in msg.parsed_msg:
        filters = ["*"]
    else:
        filters = msg.parsed_msg.get("...")
    if filters:
        logtype = type_map.get(logtype)
        if logtype:
            records = await WikiLogTargetSetInfo.get_by_target_id(msg)
            infos = records.infos
            wiki_info = WikiLib(apilink)
            status = await wiki_info.check_wiki_available()
            if status.available:
                wiki_name = status.value.name
                if status.value.lang:
                    wiki_name += f" ({status.value.lang})"
                if status.value.api in infos:
                    await records.set_filters(status.value.api, logtype, filters)
                    await msg.finish(
                        I18NContext(
                            "wikilog.message.filter.set.success",
                            wiki=wiki_name,
                            logtype=logtype,
                            filters="\n".join(filters),
                        )
                    )
                else:
                    await msg.finish(I18NContext("wikilog.message.filter.set.failed"))
            else:
                await msg.finish(
                    I18NContext(
                        "wikilog.message.enable.log.failed",
                        apilink=apilink,
                        logtype=logtype,
                    )
                )
        else:
            await msg.finish(
                I18NContext(
                    "wikilog.message.enable.log.invalid_logtype", logtype=logtype
                )
            )
    else:
        await msg.finish(I18NContext("wikilog.message.filter.set.no_filter"))


@wikilog.command(
    "bot enable <apilink> {{I18N:wikilog.help.bot.enable}}", required_superuser=True
)
@wikilog.command(
    "bot disable <apilink> {{I18N:wikilog.help.bot.disable}}", required_superuser=True
)
@wikilog.command(
    "keepalive enable <apilink> {{I18N:wikilog.help.keepalive.enable}}",
    required_superuser=True,
)
@wikilog.command(
    "keepalive disable <apilink> {{I18N:wikilog.help.keepalive.disable}}",
    required_superuser=True,
)
async def _(msg: Bot.MessageSession, apilink: str):
    records = await WikiLogTargetSetInfo.get_by_target_id(msg)
    infos = records.infos
    wiki_info = WikiLib(apilink)
    status = await wiki_info.check_wiki_available()
    if status.available:
        wiki_name = status.value.name
        if status.value.lang:
            wiki_name += f" ({status.value.lang})"
        if status.value.api in infos:
            if "keepalive" in msg.parsed_msg:
                r = await records.set_keep_alive(status.value.api, "enable" in msg.parsed_msg)
            else:
                r = await records.set_use_bot(status.value.api, "enable" in msg.parsed_msg)
            if r:
                await msg.finish(
                    I18NContext(
                        "wikilog.message.config.wiki.success", wiki=wiki_name
                    )
                )
            else:
                await msg.finish(I18NContext("wikilog.message.filter.set.failed"))
        else:
            await msg.finish(I18NContext("wikilog.message.filter.set.failed"))
    else:
        await msg.finish(
            I18NContext("wikilog.message.config.wiki.failed", message=status.message)
        )


@wikilog.command("rcshow set <apilink> ... {{I18N:wikilog.help.rcshow.set}}")
@wikilog.command("rcshow reset <apilink> {{I18N:wikilog.help.rcshow.reset}}")
async def _(msg: Bot.MessageSession, apilink: str):
    if "reset" in msg.parsed_msg:
        rcshows_ = []
    else:
        rcshows_ = msg.parsed_msg.get("...")
    if rcshows:
        records = await WikiLogTargetSetInfo.get_by_target_id(msg)
        infos = orjson.loads(records.infos)
        wiki_info = WikiLib(apilink)
        status = await wiki_info.check_wiki_available()
        if status.available:
            wiki_name = status.value.name
            if status.value.lang:
                wiki_name += f" ({status.value.lang})"
            if status.value.api in infos:
                for r in rcshows_:
                    if r not in rcshows:
                        return await msg.finish(
                            I18NContext("wikilog.message.rcshow.invalid", rcshow=r)
                        )
                await records.set_rcshow(status.value.api, rcshows_)
                await msg.finish(
                    I18NContext(
                        "wikilog.message.rcshow_set.success",
                        wiki=wiki_name,
                        rcshows="\n".join(rcshows_),
                    )
                )
            else:
                await msg.finish(I18NContext("wikilog.message.filter.set.failed"))
        else:
            await msg.finish(
                I18NContext(
                    "wikilog.message.config.wiki.failed", message=status.message
                )
            )
    else:
        await msg.finish(I18NContext("wikilog.message.filter.set.no_filter"))


@wikilog.command("list {{I18N:wikilog.help.list}}")
async def _(msg: Bot.MessageSession):
    records = await WikiLogTargetSetInfo.get_by_target_id(msg)
    infos = records.infos
    text = ""
    for apilink in infos:
        text += f"{apilink}: \n"
        text += (
            msg.session_info.locale.t("wikilog.message.list.abuselog")
            + (
                msg.session_info.locale.t("wikilog.message.enabled")
                if infos[apilink]["AbuseLog"]["enable"]
                else msg.session_info.locale.t("wikilog.message.disabled")
            )
            + "\n"
        )
        text += (
            msg.session_info.locale.t("wikilog.message.filters")
            + "\n\""
            + "\" \"".join(infos[apilink]["AbuseLog"]["filters"])
            + "\""
            + "\n"
        )
        text += (
            msg.session_info.locale.t("wikilog.message.recentchanges")
            + (
                msg.session_info.locale.t("wikilog.message.enabled")
                if infos[apilink]["RecentChanges"]["enable"]
                else msg.session_info.locale.t("wikilog.message.disabled")
            )
            + "\n"
        )
        text += (
            msg.session_info.locale.t("wikilog.message.filters")
            + "\n\""
            + "\" \"".join(infos[apilink]["RecentChanges"]["filters"])
            + "\""
            + "\n"
        )
        text += (
            msg.session_info.locale.t("wikilog.message.rcshow")
            + "\n\""
            + "\" \"".join(infos[apilink]["RecentChanges"]["rcshow"])
            + "\""
            + "\n"
        )
        text += (
            msg.session_info.locale.t("wikilog.message.usebot")
            + (
                msg.session_info.locale.t("wikilog.message.enabled")
                if infos[apilink]["use_bot"]
                else msg.session_info.locale.t("wikilog.message.disabled")
            )
            + "\n"
        )
    await msg.finish(text)


@wikilog.hook("keepalive")
async def _(ctx: Bot.ModuleHookContext):
    data_ = await WikiLogTargetSetInfo.return_all_data()
    for target in data_:
        for wiki in data_[target]:
            if (
                "keep_alive" in data_[target][wiki]
                and data_[target][wiki]["keep_alive"]
            ):
                fetch_target = await Bot.fetch_target(target)
                if fetch_target:
                    session = await FetchedMessageSession.from_session_info(fetch_target)
                    try:
                        wiki_ = WikiLib(wiki)
                        await wiki_.fixup_wiki_info()
                        get_user_info = await wiki_.get_json(
                            action="query", meta="userinfo"
                        )
                        if n := get_user_info["query"]["userinfo"]["name"]:
                            await session.send_direct_message(
                                I18NContext(
                                    "wikilog.message.keepalive.logged.as",
                                    name=n,
                                    wiki=wiki_.wiki_info.name,
                                )
                            )
                    except Exception as e:
                        Logger.error(f"Keep alive failed: {e}")
                        await session.send_direct_message(
                            I18NContext("wikilog.message.keepalive.failed", link=wiki)
                        )


fetch_cache = {}


@wikilog.schedule(IntervalTrigger(seconds=60))
async def _():
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
            try:
                if wiki not in fetch_cache[id_]:
                    fetch_cache[id_][wiki] = {
                        "AbuseLog": deque(maxlen=300),
                        "RecentChanges": deque(maxlen=300),
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
                        Logger.exception()
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
                        Logger.warning("Failed to fetch wiki log:")
                        Logger.exception()
            except Exception:
                Logger.warning("Failed to fetch wiki log:")
                Logger.exception()

    matched = matched_logs

    for id_ in matched:
        ft = await Bot.fetch_target(id_)
        if ft:
            ft_session = await FetchedMessageSession.from_session_info(ft)
            for wiki in matched[id_]:
                try:
                    wiki_info = (await WikiLib(wiki).check_wiki_available()).value
                    wiki_name = f"({wiki_info.name}) "
                    if wiki_info.wikiid:
                        wiki_name = f"({wiki_info.wikiid}) "
                except Exception:
                    continue

                if matched[id_][wiki]["AbuseLog"]:
                    ab = await convert_ab_to_detailed_format(ft_session,
                                                             matched[id_][wiki]["AbuseLog"]
                                                             )
                    for x in ab:
                        await ft_session.send_direct_message(
                            f"{wiki_name}{x}" if len(matched[id_]) > 1 else x
                        )
                if matched[id_][wiki]["RecentChanges"]:
                    rc = await convert_rc_to_detailed_format(ft_session,
                                                             matched[id_][wiki]["RecentChanges"], wiki_info
                                                             )

                    for x in rc:
                        await ft_session.send_direct_message(
                            f"{wiki_name}{x}" if len(matched[id_]) > 1 else x
                        )
