import re

from core.component import module
from core.builtins import MessageSession
from .dbutils import WikiLogUtil
from modules.wiki.utils.wikilib import WikiLib

type_map = {'abuselog': 'AbuseLog', 'logevents': 'LogEvents', 'recentchanges': 'RecentChanges',
                'AbuseLog': 'AbuseLog', 'LogEvents': 'LogEvents', 'RecentChanges': 'RecentChanges',
                'ab': 'AbuseLog', 'le': 'LogEvents', 'rc': 'RecentChanges'}

letypes = ['abusefilter', 'abusefilterblockeddomainhit', 'abusefilterprivatedetails', 'block', 'checkuser-temporary-account',
           'contentmodel', 'create', 'delete', 'gblblock', 'gblrights', 'gloopcontrol', 'import', 'managetags', 'merge',
           'move', 'newusers', 'oath', 'patrol', 'protect', 'renameuser', 'rights', 'smw', 'spamblacklist', 'suppress',
           'tag', 'thanks', 'timedmediahandler', 'titleblacklist', 'upload']

rcshows = ['!anon', '!autopatrolled', '!bot', '!minor', '!patrolled', '!redirect', 'anon', 'autopatrolled', 'bot', 'minor',
           'patrolled', 'redirect', 'unpatrolled']

wikilog = module('wikilog', developers=['OasisAkari'], required_superuser=True)


@wikilog.handle('add wiki <apilink>',
                'reset wiki <apiink>',
                'remove wiki <apiink>')
async def _(msg: MessageSession, apilink: str):
    wiki_info = WikiLib(apilink)
    status = await wiki_info.check_wiki_available()
    if status.available:
        WikiLogUtil(msg).conf_wiki(status.value.api, add='add' in msg.parsed_msg, reset='reset' in msg.parsed_msg)
        await msg.finish(msg.locale.t('wikilog.message.add_wiki.success'))
    else:
        await msg.finish(msg.locale.t('wikilog.message.add_wiki.failed'))


@wikilog.handle('list')
async def list_wiki_link(msg: MessageSession):
    infos = WikiLogUtil(msg).query.infos
    # todo 图形化输出


@wikilog.handle('enable <logtype>',
                'disable <logtype>',)
async def _(msg: MessageSession, logtype: str):
    logtype = type_map.get(logtype, None)
    if logtype:
        WikiLogUtil(msg).conf_log(logtype, enable='enable' in msg.parsed_msg)
        await msg.finish(msg.locale.t('wikilog.message.enable_log.success', logtype=logtype))
    else:
        await msg.finish(msg.locale.t('wikilog.message.enable_log.invalid_logtype'))


@wikilog.handle('filter test <filter> <text>')
async def _(msg: MessageSession, filter: str, text):
    f = re.compile(filter)
    if f.search(text):
        await msg.finish(msg.locale.t('wikilog.message.filter_test.success'))
    else:
        await msg.finish(msg.locale.t('wikilog.message.filter_test.failed'))



@wikilog.handle('filter set <apilink> <logtype> ...')
async def _(msg: MessageSession, apilink: str, logtype: str):
    filters = msg.parsed_msg.get('...')
    if filters:
        logtype = type_map.get(logtype, None)
        if logtype:
            t = WikiLogUtil(msg)
            infos = t.query.infos
            if apilink in infos:
                t.set_filters(apilink, logtype, filters)
                await msg.finish(msg.locale.t('wikilog.message.filter_set.success'))
            else:
                await msg.finish(msg.locale.t('wikilog.message.filter_set.invalid_apilink'))
        else:
            await msg.finish(msg.locale.t('wikilog.message.filter_set.invalid_logtype'))
    else:
        await msg.finish(msg.locale.t('wikilog.message.filter_set.no_filter'))


@wikilog.handle('enable bot <apilink>')
@wikilog.handle('disable bot <apilink>')
async def _(msg: MessageSession, apilink: str):
    t = WikiLogUtil(msg)
    infos = t.query.infos
    if apilink in infos:
        t.set_use_bot(apilink, 'enable' in msg.parsed_msg)
    else:
        await msg.finish(msg.locale.t('wikilog.message.use_bot.invalid_apilink'))


@wikilog.handle('letype set <apilink> ...')
async def _(msg: MessageSession, apilink: str):
    letypes = msg.parsed_msg.get('...')
    if letypes:
        t = WikiLogUtil(msg)
        infos = t.query.infos
        if apilink in infos:
            t.set_letypes(apilink, letypes)
            await msg.finish(msg.locale.t('wikilog.message.letype_set.success'))
        else:
            await msg.finish(msg.locale.t('wikilog.message.letype_set.invalid_apilink'))
    else:
        await msg.finish(msg.locale.t('wikilog.message.letype_set.no_letype'))


@wikilog.handle('rcshow set <apilink> ...')
async def _(msg: MessageSession, apilink: str):
    rcshows = msg.parsed_msg.get('...')
    if rcshows:
        t = WikiLogUtil(msg)
        infos = t.query.infos
        if apilink in infos:
            t.set_rcshows(apilink, rcshows)
            await msg.finish(msg.locale.t('wikilog.message.rcshow_set.success'))
        else:
            await msg.finish(msg.locale.t('wikilog.message.rcshow_set.invalid_apilink'))
    else:
        await msg.finish(msg.locale.t('wikilog.message.rcshow_set.no_rcshow'))
