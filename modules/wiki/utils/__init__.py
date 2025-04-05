import re
import traceback

from core.builtins import Bot
from core.component import module
from core.logger import Logger
from modules.wiki.database.models import WikiTargetInfo
from .ab import ab
from .ab_qq import ab_qq
from .newbie import newbie
from .rc import rc
from .rc_qq import rc_qq
from .user import get_user_info

rc_ = module("rc", developers=["OasisAkari"], recommend_modules="wiki", doc=True)


@rc_.command()
@rc_.command("[--legacy] {{wiki.help.rc}}",
             options_desc={"--legacy": "{help.option.legacy}"},
             available_for=["QQ|Group"]
             )
async def _(msg: Bot.MessageSession):
    target = (await WikiTargetInfo.get_or_create(target_id=msg.target.target_id))[0]
    start_wiki = target.api_link
    if not start_wiki:
        await msg.finish(msg.locale.t("wiki.message.not_set"))
    legacy = True
    if not msg.parsed_msg and msg.Feature.forward:
        from bots.aiocqhttp.utils import get_onebot_implementation

        obi = await get_onebot_implementation()
        if obi in ["napcat", "llonebot"]:
            try:
                await msg.send_message(
                    msg.locale.t("wiki.message.ntqq.forward.sending")
                )
                nodelist = await rc_qq(msg, start_wiki)
                await msg.fake_forward_msg(nodelist)
            except ValueError:
                await msg.send_message(msg.locale.t("wiki.message.rollback"))
            except Exception:
                await msg.send_message(
                    msg.locale.t("wiki.message.ntqq.forward.timeout")
                )
            legacy = False
        else:
            try:
                nodelist = await rc_qq(msg, start_wiki)
                await msg.fake_forward_msg(nodelist)
                legacy = False
            except Exception:
                Logger.error(traceback.format_exc())
                await msg.send_message(msg.locale.t("wiki.message.rollback"))
    if legacy:
        try:
            res = await rc(msg, start_wiki)
            await msg.finish(res)
        except Exception:
            Logger.error(traceback.format_exc())
            await msg.finish(msg.locale.t("wiki.message.error.fetch_log"))


@rc_.command("{{wiki.help.rc}}", exclude_from=["QQ|Group"])
async def _(msg: Bot.MessageSession):
    target = (await WikiTargetInfo.get_or_create(target_id=msg.target.target_id))[0]
    start_wiki = target.api_link
    if not start_wiki:
        await msg.finish(msg.locale.t("wiki.message.not_set"))
    try:
        res = await rc(msg, start_wiki)
        await msg.finish(res)
    except Exception:
        Logger.error(traceback.format_exc())
        await msg.finish(msg.locale.t("wiki.message.error.fetch_log"))


ab_ = module("ab", developers=["OasisAkari"], recommend_modules="wiki", doc=True)


@ab_.command()
@ab_.command("[--legacy] {{wiki.help.ab}}",
             options_desc={"--legacy": "{help.option.legacy}"},
             available_for=["QQ|Group"]
             )
async def _(msg: Bot.MessageSession):
    target = (await WikiTargetInfo.get_or_create(target_id=msg.target.target_id))[0]
    start_wiki = target.api_link
    if not start_wiki:
        await msg.finish(msg.locale.t("wiki.message.not_set"))
    legacy = True
    if not msg.parsed_msg and msg.Feature.forward:
        from bots.aiocqhttp.utils import get_onebot_implementation

        obi = await get_onebot_implementation()
        if obi in ["napcat", "llonebot"]:
            try:
                await msg.send_message(
                    msg.locale.t("wiki.message.ntqq.forward.sending")
                )
                nodelist = await ab_qq(msg, start_wiki)
                await msg.fake_forward_msg(nodelist)
            except ValueError:
                await msg.send_message(msg.locale.t("wiki.message.rollback"))
            except Exception:
                await msg.send_message(
                    msg.locale.t("wiki.message.ntqq.forward.timeout")
                )
            legacy = False
        else:
            try:
                nodelist = await ab_qq(msg, start_wiki)
                await msg.fake_forward_msg(nodelist)
                legacy = False
            except Exception:
                Logger.error(traceback.format_exc())
                await msg.send_message(msg.locale.t("wiki.message.rollback"))
    if legacy:
        try:
            res = await ab(msg, start_wiki)
            await msg.finish(res)
        except Exception:
            Logger.error(traceback.format_exc())
            await msg.finish(msg.locale.t("wiki.message.error.fetch_log"))


@ab_.command("{{wiki.help.ab}}", exclude_from=["QQ|Group"])
async def _(msg: Bot.MessageSession):
    target = (await WikiTargetInfo.get_or_create(target_id=msg.target.target_id))[0]
    start_wiki = target.api_link
    if not start_wiki:
        await msg.finish(msg.locale.t("wiki.message.not_set"))
    try:
        res = await ab(msg, start_wiki)
        await msg.finish(res)
    except Exception:
        Logger.error(traceback.format_exc())
        await msg.finish(msg.locale.t("wiki.message.error.fetch_log"))


new = module("newbie", developers=["OasisAkari"], recommend_modules="wiki", doc=True)


@new.command("{{wiki.help.newbie}}")
async def _(msg: Bot.MessageSession):
    target = (await WikiTargetInfo.get_or_create(target_id=msg.target.target_id))[0]
    start_wiki = target.api_link
    if not start_wiki:
        await msg.finish(msg.locale.t("wiki.message.not_set"))
    try:
        res = await newbie(msg, start_wiki)
        await msg.finish(res)
    except Exception:
        Logger.error(traceback.format_exc())
        await msg.finish(msg.locale.t("wiki.message.error.fetch_log"))


usr = module("user", developers=["OasisAkari"], recommend_modules="wiki", doc=True)


@usr.command("<username> {{wiki.help.user}}")
async def _(msg: Bot.MessageSession, username: str):
    target = (await WikiTargetInfo.get_or_create(target_id=msg.target.target_id))[0]
    start_wiki = target.api_link
    if start_wiki:
        match_interwiki = re.match(r"(.*?):(.*)", username)
        if match_interwiki:
            interwikis = target.interwikis
            if match_interwiki.group(1) in interwikis:
                await get_user_info(
                    msg, interwikis[match_interwiki.group(1)], match_interwiki.group(2)
                )
        await get_user_info(msg, start_wiki, username)
    else:
        await msg.finish(msg.locale.t("wiki.message.not_set"))
