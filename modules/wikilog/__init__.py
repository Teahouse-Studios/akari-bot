import re

import orjson as json

from core.builtins import Bot, I18NContext
from core.component import module
from core.config import Config
from core.constants import Info, wiki_whitelist_url_default
from core.logger import Logger
from modules.wiki.utils.wikilib import WikiLib
from .utils import convert_data_to_text
from ..wiki.utils.ab import convert_ab_to_detailed_format
from ..wiki.utils.rc import convert_rc_to_detailed_format
from .database.models import WikiLogTargetSetInfo

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
    "add wiki <apilink> {{wikilog.help.add.wiki}}",
    "reset wiki <apilink> {{wikilog.help.reset.wiki}}",
    "remove wiki <apilink> {{wikilog.help.remove.wiki}}",
)
async def _(msg: Bot.MessageSession, apilink: str):
    wiki_info = WikiLib(apilink)
    status = await wiki_info.check_wiki_available()
    in_allowlist = True
    if Info.use_url_manager:
        in_allowlist = status.value.in_allowlist
        if status.value.in_blocklist and not in_allowlist:
            await msg.finish(
                msg.locale.t("wiki.message.invalid.blocked", name=status.value.name)
            )
    if not in_allowlist:
        prompt = msg.locale.t("wikilog.message.untrust.wiki", name=status.value.name)
        if wiki_whitelist_url:
            prompt += "\n" + msg.locale.t("wiki.message.wiki_audit.untrust.address", url=wiki_whitelist_url)
        await msg.finish(prompt)
        return
    if status.available:
        records = await WikiLogTargetSetInfo.get_by_target_id(target_id=msg)
        await records.conf_wiki(
            status.value.api,
            add="add" in msg.parsed_msg,
            reset="reset" in msg.parsed_msg,
        )
        await msg.finish(
            msg.locale.t("wikilog.message.config.wiki.success", wiki=status.value.name)
        )
    else:
        await msg.finish(
            msg.locale.t("wikilog.message.config.wiki.failed", message=status.message)
        )


@wikilog.command(
    "enable <apilink> <logtype> {{wikilog.help.enable.logtype}}",
    "disable <apilink> <logtype> {{wikilog.help.disable.logtype}}",
)
async def _(msg: Bot.MessageSession, apilink, logtype: str):
    logtype = type_map.get(logtype)
    if logtype:
        wiki_info = WikiLib(apilink)
        status = await wiki_info.check_wiki_available()
        if status.available:
            records = await WikiLogTargetSetInfo.get_by_target_id(target_id=msg)
            if records.conf_log(
                status.value.api, logtype, enable="enable" in msg.parsed_msg
            ):
                await msg.finish(
                    msg.locale.t(
                        "wikilog.message.enable.log.success",
                        wiki=status.value.name,
                        logtype=logtype,
                    )
                )
            else:
                await msg.finish(
                    msg.locale.t(
                        "wikilog.message.enable.log.failed",
                        apilink=apilink,
                        logtype=logtype,
                    )
                )
        else:
            await msg.finish(
                msg.locale.t(
                    "wikilog.message.enable.log.failed",
                    apilink=apilink,
                    logtype=logtype,
                )
            )
    else:
        await msg.finish(
            msg.locale.t("wikilog.message.enable.log.invalid_logtype", logtype=logtype)
        )


@wikilog.command("filter test <filters> <example> {{wikilog.help.filter.test}}")
async def _(msg: Bot.MessageSession, filters: str, example: str):
    f = re.compile(filters)
    if m := f.search(example):
        await msg.finish(
            msg.locale.t(
                "wikilog.message.filter.test.success",
                start=m.start(),
                end=m.end(),
                string=example[m.start(): m.end()],
            )
        )
    else:
        await msg.finish(msg.locale.t("wikilog.message.filter.test.failed"))


@wikilog.command("filter example <example> {{wikilog.help.filter.example}}")
async def _(msg: Bot.MessageSession):
    try:
        example = msg.trigger_msg.replace("wikilog filter example ", "", 1)
        Logger.debug(example)
        load = json.loads(example)
        await msg.send_message(convert_data_to_text(load))
    except Exception:
        await msg.send_message(msg.locale.t("wikilog.message.filter.example.invalid"))


@wikilog.command("api get <apilink> <logtype> {{wikilog.help.api.get}}")
async def _(msg: Bot.MessageSession, apilink, logtype):
    records = await WikiLogTargetSetInfo.get_by_target_id(target_id=msg)
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
            await msg.finish(msg.locale.t("wikilog.message.filter.set.failed"))
    else:
        await msg.finish(
            msg.locale.t(
                "wikilog.message.enable.log.failed", apilink=apilink, logtype=logtype
            )
        )


@wikilog.command("filter set <apilink> <logtype> ... {{wikilog.help.filter.set}}")
@wikilog.command("filter reset <apilink> <logtype> {{wikilog.help.filter.reset}}")
async def _(msg: Bot.MessageSession, apilink: str, logtype: str):
    if "reset" in msg.parsed_msg:
        filters = ["*"]
    else:
        filters = msg.parsed_msg.get("...")
    if filters:
        logtype = type_map.get(logtype)
        if logtype:
            records = await WikiLogTargetSetInfo.get_by_target_id(target_id=msg)
            infos = records.infos
            wiki_info = WikiLib(apilink)
            status = await wiki_info.check_wiki_available()
            if status.available:
                if status.value.api in infos:
                    await records.set_filters(status.value.api, logtype, filters)
                    await msg.finish(
                        msg.locale.t(
                            "wikilog.message.filter.set.success",
                            wiki=status.value.name,
                            logtype=logtype,
                            filters="\n".join(filters),
                        )
                    )
                else:
                    await msg.finish(msg.locale.t("wikilog.message.filter.set.failed"))
            else:
                await msg.finish(
                    msg.locale.t(
                        "wikilog.message.enable.log.failed",
                        apilink=apilink,
                        logtype=logtype,
                    )
                )
        else:
            await msg.finish(
                msg.locale.t(
                    "wikilog.message.enable.log.invalid_logtype", logtype=logtype
                )
            )
    else:
        await msg.finish(msg.locale.t("wikilog.message.filter.set.no_filter"))


@wikilog.command(
    "bot enable <apilink> {{wikilog.help.bot.enable}}", required_superuser=True
)
@wikilog.command(
    "bot disable <apilink> {{wikilog.help.bot.disable}}", required_superuser=True
)
@wikilog.command(
    "keepalive enable <apilink> {{wikilog.help.keepalive.enable}}",
    required_superuser=True,
)
@wikilog.command(
    "keepalive disable <apilink> {{wikilog.help.keepalive.disable}}",
    required_superuser=True,
)
async def _(msg: Bot.MessageSession, apilink: str):
    records = await WikiLogTargetSetInfo.get_by_target_id(target_id=msg)
    infos = records.infos
    wiki_info = WikiLib(apilink)
    status = await wiki_info.check_wiki_available()
    if status.available:
        if status.value.api in infos:
            if "keepalive" in msg.parsed_msg:
                r = await records.set_keep_alive(status.value.api, "enable" in msg.parsed_msg)
            else:
                r = await records.set_use_bot(status.value.api, "enable" in msg.parsed_msg)
            if r:
                await msg.finish(
                    msg.locale.t(
                        "wikilog.message.config.wiki.success", wiki=status.value.name
                    )
                )
            else:
                await msg.finish(msg.locale.t("wikilog.message.filter.set.failed"))
        else:
            await msg.finish(msg.locale.t("wikilog.message.filter.set.failed"))
    else:
        await msg.finish(
            msg.locale.t("wikilog.message.config.wiki.failed", message=status.message)
        )


@wikilog.command("rcshow set <apilink> ... {{wikilog.help.rcshow.set}}")
@wikilog.command("rcshow reset <apilink> {{wikilog.help.rcshow.reset}}")
async def _(msg: Bot.MessageSession, apilink: str):
    if "reset" in msg.parsed_msg:
        rcshows_ = []
    else:
        rcshows_ = msg.parsed_msg.get("...")
    if rcshows:
        records = await WikiLogTargetSetInfo.get_by_target_id(target_id=msg)
        infos = json.loads(records.infos)
        wiki_info = WikiLib(apilink)
        status = await wiki_info.check_wiki_available()
        if status.available:
            if status.value.api in infos:
                for r in rcshows_:
                    if r not in rcshows:
                        return await msg.finish(
                            msg.locale.t("wikilog.message.rcshow.invalid", rcshow=r)
                        )
                await records.set_rcshow(status.value.api, rcshows_)
                await msg.finish(
                    msg.locale.t(
                        "wikilog.message.rcshow_set.success",
                        wiki=status.value.name,
                        rcshows="\n".join(rcshows_),
                    )
                )
            else:
                await msg.finish(msg.locale.t("wikilog.message.filter.set.failed"))
        else:
            await msg.finish(
                msg.locale.t(
                    "wikilog.message.config.wiki.failed", message=status.message
                )
            )
    else:
        await msg.finish(msg.locale.t("wikilog.message.filter.set.no_filter"))


@wikilog.command("list {{wikilog.help.list}}")
async def _(msg: Bot.MessageSession):
    records = await WikiLogTargetSetInfo.get_by_target_id(target_id=msg)
    infos = records.infos
    text = ""
    for apilink in infos:
        text += f"{apilink}: \n"
        text += (
            msg.locale.t("wikilog.message.list.abuselog")
            + (
                msg.locale.t("wikilog.message.enabled")
                if infos[apilink]["AbuseLog"]["enable"]
                else msg.locale.t("wikilog.message.disabled")
            )
            + "\n"
        )
        text += (
            msg.locale.t("wikilog.message.filters")
            + "\n\""
            + "\" \"".join(infos[apilink]["AbuseLog"]["filters"])
            + "\""
            + "\n"
        )
        text += (
            msg.locale.t("wikilog.message.recentchanges")
            + (
                msg.locale.t("wikilog.message.enabled")
                if infos[apilink]["RecentChanges"]["enable"]
                else msg.locale.t("wikilog.message.disabled")
            )
            + "\n"
        )
        text += (
            msg.locale.t("wikilog.message.filters")
            + "\n\""
            + "\" \"".join(infos[apilink]["RecentChanges"]["filters"])
            + "\""
            + "\n"
        )
        text += (
            msg.locale.t("wikilog.message.rcshow")
            + "\n\""
            + "\" \"".join(infos[apilink]["RecentChanges"]["rcshow"])
            + "\""
            + "\n"
        )
        text += (
            msg.locale.t("wikilog.message.usebot")
            + (
                msg.locale.t("wikilog.message.enabled")
                if infos[apilink]["use_bot"]
                else msg.locale.t("wikilog.message.disabled")
            )
            + "\n"
        )
    await msg.finish(text)


@wikilog.hook("matched")
async def _(fetch: Bot.FetchTarget, ctx: Bot.ModuleHookContext):
    matched = ctx.args["matched_logs"]
    Logger.debug("Received matched_logs hook: " + str(matched))
    for id_ in matched:
        ft = await fetch.fetch_target(id_)
        if ft:
            for wiki in matched[id_]:
                wiki_info = (await WikiLib(wiki).check_wiki_available()).value
                if matched[id_][wiki]["AbuseLog"]:
                    ab = await convert_ab_to_detailed_format(
                        matched[id_][wiki]["AbuseLog"], ft.parent
                    )
                    for x in ab:
                        await ft.send_direct_message(
                            f"{wiki_info.name}\n{x}" if len(matched[id_]) > 1 else x
                        )
                if matched[id_][wiki]["RecentChanges"]:
                    rc = await convert_rc_to_detailed_format(
                        matched[id_][wiki]["RecentChanges"], wiki_info, ft.parent
                    )

                    for x in rc:
                        await ft.send_direct_message(
                            f"{wiki_info.name}\n{x}" if len(matched[id_]) > 1 else x
                        )


@wikilog.hook("keepalive")
async def _(fetch: Bot.FetchTarget, ctx: Bot.ModuleHookContext):
    data_ = await WikiLogTargetSetInfo.return_all_data()
    for target in data_:
        for wiki in data_[target]:
            if (
                "keep_alive" in data_[target][wiki]
                and data_[target][wiki]["keep_alive"]
            ):
                fetch_target = await fetch.fetch_target(target)
                if fetch_target:
                    try:
                        wiki_ = WikiLib(wiki)
                        await wiki_.fixup_wiki_info()
                        get_user_info = await wiki_.get_json(
                            action="query", meta="userinfo"
                        )
                        if n := get_user_info["query"]["userinfo"]["name"]:
                            await fetch_target.send_direct_message(
                                I18NContext(
                                    "wikilog.message.keepalive.logged.as",
                                    name=n,
                                    wiki=wiki_.wiki_info.name,
                                )
                            )
                    except Exception as e:
                        Logger.error(f"Keep alive failed: {e}")
                        await fetch_target.send_direct_message(
                            I18NContext("wikilog.message.keepalive.failed", link=wiki)
                        )
