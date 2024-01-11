import traceback

from core.builtins import Bot
from core.component import module
from modules.wiki.utils.dbutils import WikiTargetInfo, Audit
from modules.wiki.utils.wikilib import WikiLib, WhatAreUDoingError, PageInfo, InvalidWikiError, QueryInfo
from .ab import ab
from .ab_qq import ab_qq
from .newbie import newbie
from .rc import rc
from .rc_qq import rc_qq

rc_ = module('rc', developers=['OasisAkari'], recommend_modules='wiki')


@rc_.command(['{{wiki.help.rc}}',
              'legacy {{wiki.help.rc.legacy}}'],
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


a = module('ab', developers=['OasisAkari'], recommend_modules='wiki')


@a.command(['{{wiki.help.ab}}',
            'legacy {{wiki.help.ab.legacy}}'],
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
            traceback.print_exc()
            await msg.send_message(msg.locale.t('wiki.message.rollback'))
    if legacy:
        try:
            res = await ab(msg, start_wiki)
            await msg.finish(res)
        except Exception:
            traceback.print_exc()
            await msg.send_message(msg.locale.t('wiki.message.error.fetch_log'))


@a.command('{{wiki.help.ab}}',
           exclude_from=['QQ', 'QQ|Group'])
async def ab_loader(msg: Bot.MessageSession):
    start_wiki = WikiTargetInfo(msg).get_start_wiki()
    if not start_wiki:
        await msg.finish(msg.locale.t('wiki.message.not_set'))
    try:
        res = await ab(msg, start_wiki)
        await msg.finish(res)
    except Exception:
        traceback.print_exc()
        await msg.send_message(msg.locale.t('wiki.message.error.fetch_log'))


n = module('newbie', developers=['OasisAkari'], recommend_modules='wiki')


@n.command('{{wiki.help.newbie}}')
async def newbie_loader(msg: Bot.MessageSession):
    start_wiki = WikiTargetInfo(msg).get_start_wiki()
    if not start_wiki:
        await msg.finish(msg.locale.t('wiki.message.not_set'))
    try:
        res = await newbie(msg, start_wiki)
        await msg.finish(res)
    except Exception:
        traceback.print_exc()
        await msg.send_message(msg.locale.t('wiki.message.error.fetch_log'))
