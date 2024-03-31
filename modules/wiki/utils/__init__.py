import traceback

from core.builtins import Bot
from core.component import module
from core.logger import Logger
from modules.wiki.utils.dbutils import WikiTargetInfo, Audit
from modules.wiki.utils.wikilib import WikiLib, WhatAreUDoingError, PageInfo, InvalidWikiError, QueryInfo
from .ab import ab
from .ab_qq import ab_qq
from .newbie import newbie
from .rc import rc
from .rc_qq import rc_qq

rc_ = module('rc', developers=['OasisAkari'], recommend_modules='wiki')


@rc_.command()
@rc_.command('[-l] {{wiki.help.rc}}',
             options_desc={'-l': '{help.option.l}'},
             available_for=['QQ', 'QQ|Group'])
async def rc_loader(msg: Bot.MessageSession):
    start_wiki = WikiTargetInfo(msg).get_start_wiki()
    if not start_wiki:
        await msg.finish(msg.locale.t('wiki.message.not_set'))
    legacy = True
    if not msg.parsed_msg and msg.Feature.forward and msg.target.target_from == 'QQ|Group':
        try:
            nodelist = await rc_qq(msg, start_wiki)
            await msg.fake_forward_msg(nodelist)
            legacy = False
        except Exception:
            traceback.print_exc()
            await msg.send_message(msg.locale.t('wiki.message.rollback'))
    if legacy:
        res = await rc(msg, start_wiki)
        await msg.finish(res)


@rc_.command('{{wiki.help.rc}}',
             exclude_from=['QQ', 'QQ|Group'])
async def rc_loader(msg: Bot.MessageSession):
    start_wiki = WikiTargetInfo(msg).get_start_wiki()
    if not start_wiki:
        await msg.finish(msg.locale.t('wiki.message.not_set'))
    res = await rc(msg, start_wiki)
    await msg.finish(res)


ab_ = module('ab', developers=['OasisAkari'], recommend_modules='wiki')


@ab_.command()
@ab_.command('[-l] {{wiki.help.ab}}',
             options_desc={'-l': '{help.option.l}'},
             available_for=['QQ', 'QQ|Group'])
async def ab_loader(msg: Bot.MessageSession):
    start_wiki = WikiTargetInfo(msg).get_start_wiki()
    if not start_wiki:
        await msg.finish(msg.locale.t('wiki.message.not_set'))
    legacy = True
    if not msg.parsed_msg and msg.Feature.forward and msg.target.target_from == 'QQ|Group':
        try:
            nodelist = await ab_qq(msg, start_wiki)
            await msg.fake_forward_msg(nodelist)
            legacy = False
        except Exception:
            Logger.error(traceback.format_exc())
            await msg.send_message(msg.locale.t('wiki.message.rollback'))
    if legacy:
        try:
            res = await ab(msg, start_wiki)
            await msg.finish(res)
        except Exception:
            Logger.error(traceback.format_exc())
            await msg.finish(msg.locale.t('wiki.message.error.fetch_log'))


@ab_.command('{{wiki.help.ab}}',
             exclude_from=['QQ', 'QQ|Group'])
async def ab_loader(msg: Bot.MessageSession):
    start_wiki = WikiTargetInfo(msg).get_start_wiki()
    if not start_wiki:
        await msg.finish(msg.locale.t('wiki.message.not_set'))
    try:
        res = await ab(msg, start_wiki)
        await msg.finish(res)
    except Exception:
        Logger.error(traceback.format_exc())
        await msg.finish(msg.locale.t('wiki.message.error.fetch_log'))


new = module('newbie', developers=['OasisAkari'], recommend_modules='wiki')


@new.command('{{wiki.help.newbie}}')
async def newbie_loader(msg: Bot.MessageSession):
    start_wiki = WikiTargetInfo(msg).get_start_wiki()
    if not start_wiki:
        await msg.finish(msg.locale.t('wiki.message.not_set'))
    try:
        res = await newbie(msg, start_wiki)
        await msg.finish(res)
    except Exception:
        Logger.error(traceback.format_exc())
        await msg.finish(msg.locale.t('wiki.message.error.fetch_log'))
