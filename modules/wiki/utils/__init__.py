import re

from aiocqhttp.exceptions import NetworkError

from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext
from core.component import module
from core.logger import Logger
from core.utils.forward import check_enable_forward_msg
from modules.wiki.database.models import WikiTargetInfo
from .ab import get_ab
from .ab_qq import get_ab_qq
from .newbie import get_newbie
from .rc import get_rc
from .rc_qq import get_rc_qq
from .user import get_user_info

rc_ = module("rc", developers=["OasisAkari"], recommend_modules="wiki", doc=True)


@rc_.command()
@rc_.command("[--legacy] {{I18N:wiki.help.rc}}",
             options_desc={"--legacy": "{I18N:help.option.legacy}"},
             available_for=["QQ|Group", "QQ|Private"]
             )
async def _(msg: Bot.MessageSession):
    target = await WikiTargetInfo.get_by_target_id(msg.session_info.target_id)
    start_wiki = target.api_link
    headers = target.headers
    if not start_wiki:
        await msg.finish(I18NContext("wiki.message.not_set"))
    legacy = True
    if not msg.parsed_msg and msg.session_info.support_forward and await check_enable_forward_msg():
        if msg.session_info.tmp.get("onebot_impl") in ["napcat", "llonebot"]:
            try:
                await msg.send_message(I18NContext("wiki.message.ntqq.forward.sending"))
                nodelist = await get_rc_qq(msg, start_wiki, headers)
                await msg.send_message(nodelist)
                legacy = False
            except NetworkError:
                legacy = False
                await msg.send_message(I18NContext("wiki.message.ntqq.forward.timeout"))
            except Exception:
                Logger.exception()
                await msg.send_message(I18NContext("wiki.message.rollback"))
        else:
            try:
                nodelist = await get_rc_qq(msg, start_wiki, headers)
                await msg.send_message(nodelist)
                legacy = False
            except Exception:
                Logger.exception()
                await msg.send_message(I18NContext("wiki.message.rollback"))
    if legacy:
        try:
            res = await get_rc(msg, start_wiki, headers)
            await msg.finish(res)
        except Exception:
            Logger.exception()
            await msg.finish(I18NContext("wiki.message.error.fetch_log"))


@rc_.command("{{I18N:wiki.help.rc}}",
             exclude_from=["QQ|Group", "QQ|Private"]
             )
async def _(msg: Bot.MessageSession):
    target = await WikiTargetInfo.get_by_target_id(msg.session_info.target_id)
    start_wiki = target.api_link
    headers = target.headers
    if not start_wiki:
        await msg.finish(I18NContext("wiki.message.not_set"))
    try:
        res = await get_rc(msg, start_wiki, headers)
        await msg.finish(res)
    except Exception:
        Logger.exception()
        await msg.finish(I18NContext("wiki.message.error.fetch_log"))


ab_ = module("ab", developers=["OasisAkari"], recommend_modules="wiki", doc=True)


@ab_.command()
@ab_.command("[--legacy] {{I18N:wiki.help.ab}}",
             options_desc={"--legacy": "{I18N:help.option.legacy}"},
             available_for=["QQ|Group", "QQ|Private"]
             )
async def _(msg: Bot.MessageSession):
    target = await WikiTargetInfo.get_by_target_id(msg.session_info.target_id)
    start_wiki = target.api_link
    headers = target.headers
    if not start_wiki:
        await msg.finish(I18NContext("wiki.message.not_set"))
    legacy = True
    if not msg.parsed_msg and msg.session_info.support_forward and await check_enable_forward_msg():
        if msg.session_info.tmp.get("onebot_impl") in ["napcat", "llonebot"]:
            try:
                await msg.send_message(I18NContext("wiki.message.ntqq.forward.sending"))
                nodelist = await get_ab_qq(msg, start_wiki, headers)
                await msg.send_message(nodelist)
                legacy = False
            except NetworkError:
                legacy = False
                await msg.send_message(I18NContext("wiki.message.ntqq.forward.timeout"))
            except Exception:
                Logger.exception()
                await msg.send_message(I18NContext("wiki.message.rollback"))
        else:
            try:
                nodelist = await get_ab_qq(msg, start_wiki, headers)
                await msg.send_message(nodelist)
                legacy = False
            except Exception:
                Logger.exception()
                await msg.send_message(I18NContext("wiki.message.rollback"))
    if legacy:
        try:
            res = await get_ab(msg, start_wiki, headers)
            await msg.finish(res)
        except Exception:
            Logger.exception()
            await msg.finish(I18NContext("wiki.message.error.fetch_log"))


@ab_.command("{{I18N:wiki.help.ab}}",
             exclude_from=["QQ|Group", "QQ|Private"]
             )
async def _(msg: Bot.MessageSession):
    target = await WikiTargetInfo.get_by_target_id(msg.session_info.target_id)
    start_wiki = target.api_link
    headers = target.headers
    if not start_wiki:
        await msg.finish(I18NContext("wiki.message.not_set"))
    try:
        res = await get_ab(msg, start_wiki, headers)
        await msg.finish(res)
    except Exception:
        Logger.exception()
        await msg.finish(I18NContext("wiki.message.error.fetch_log"))


new = module("newbie", developers=["OasisAkari"], recommend_modules="wiki", doc=True)


@new.command("{{I18N:wiki.help.newbie}}")
async def _(msg: Bot.MessageSession):
    target = await WikiTargetInfo.get_by_target_id(msg.session_info.target_id)
    start_wiki = target.api_link
    headers = target.headers
    if not start_wiki:
        await msg.finish(I18NContext("wiki.message.not_set"))
    try:
        res = await get_newbie(start_wiki, headers, session=msg)
        await msg.finish(res)
    except Exception:
        Logger.exception()
        await msg.finish(I18NContext("wiki.message.error.fetch_log"))


usr = module("user", developers=["OasisAkari"], recommend_modules="wiki", doc=True)


@usr.command("<username> {{I18N:wiki.help.user}}")
async def _(msg: Bot.MessageSession, username: str):
    target = await WikiTargetInfo.get_by_target_id(msg.session_info.target_id)
    start_wiki = target.api_link
    headers = target.headers
    if start_wiki:
        match_interwiki = re.match(r"(.*?):(.*)", username)
        if match_interwiki:
            interwikis = target.interwikis
            if match_interwiki.group(1) in interwikis:
                await msg.finish(await get_user_info(
                    msg, match_interwiki.group(2), interwikis[match_interwiki.group(1)], headers
                ))
        await msg.finish(await get_user_info(msg, username, start_wiki, headers))
    else:
        await msg.finish(I18NContext("wiki.message.not_set"))
