import re
import traceback
import urllib.parse

from core.component import module
from core.builtins import Bot, FormattedTime
from core.dirty_check import check as dirty_check
from core.logger import Logger
from .dbutils import WikiLogUtil
from modules.wiki.utils.wikilib import WikiLib, WikiInfo
import ujson as json

from ..wiki.utils.rc import convert_rc_to_detailed_format
from ..wiki.utils.time import strptime2ts

type_map = {'abuselog': 'AbuseLog', 'recentchanges': 'RecentChanges',
            'AbuseLog': 'AbuseLog', 'RecentChanges': 'RecentChanges',
            'ab': 'AbuseLog', 'rc': 'RecentChanges'}


rcshows = [
    '!anon',
    '!autopatrolled',
    '!bot',
    '!minor',
    '!patrolled',
    '!redirect',
    'anon',
    'autopatrolled',
    'bot',
    'minor',
    'patrolled',
    'redirect',
    'unpatrolled']

wikilog = module('wikilog', developers=['OasisAkari'], required_superuser=True)


@wikilog.handle('add wiki <apilink>',
                'reset wiki <apiink>',
                'remove wiki <apiink>')
async def _(msg: Bot.MessageSession, apilink: str):
    wiki_info = WikiLib(apilink)
    status = await wiki_info.check_wiki_available()
    if status.available:
        WikiLogUtil(msg).conf_wiki(status.value.api, add='add' in msg.parsed_msg, reset='reset' in msg.parsed_msg)
        await msg.finish(msg.locale.t('wikilog.message.add_wiki.success'))
    else:
        await msg.finish(msg.locale.t('wikilog.message.add_wiki.failed'))


@wikilog.handle('enable <apilink> <logtype>',
                'disable <apilink> <logtype>')
async def _(msg: Bot.MessageSession, apilink, logtype: str):
    logtype = type_map.get(logtype, None)
    if logtype:
        wiki_info = WikiLib(apilink)
        status = await wiki_info.check_wiki_available()
        if WikiLogUtil(msg).conf_log(status.value.api, logtype, enable='enable' in msg.parsed_msg):
            await msg.finish(msg.locale.t('wikilog.message.enable_log.success', logtype=logtype))
        else:
            await msg.finish(msg.locale.t('wikilog.message.enable_log.failed', logtype=logtype))
    else:
        await msg.finish(msg.locale.t('wikilog.message.enable_log.invalid_logtype'))


@wikilog.handle('filter test <filter> <text>')
async def _(msg: Bot.MessageSession, filter: str, text):
    f = re.compile(filter)
    if f.search(text):
        await msg.finish(msg.locale.t('wikilog.message.filter_test.success'))
    else:
        await msg.finish(msg.locale.t('wikilog.message.filter_test.failed'))


@wikilog.handle('filter set <apilink> <logtype> ...')
async def _(msg: Bot.MessageSession, apilink: str, logtype: str):
    filters = msg.parsed_msg.get('...')
    if filters:
        logtype = type_map.get(logtype, None)
        if logtype:
            t = WikiLogUtil(msg)
            infos = json.loads(t.query.infos)
            wiki_info = WikiLib(apilink)
            status = await wiki_info.check_wiki_available()
            if status.value.api in infos:
                t.set_filters(status.value.api, logtype, filters)
                await msg.finish(msg.locale.t('wikilog.message.filter_set.success'))
            else:
                await msg.finish(msg.locale.t('wikilog.message.filter_set.invalid_apilink'))
        else:
            await msg.finish(msg.locale.t('wikilog.message.filter_set.invalid_logtype'))
    else:
        await msg.finish(msg.locale.t('wikilog.message.filter_set.no_filter'))


@wikilog.handle('enable bot <apilink>')
@wikilog.handle('disable bot <apilink>')
async def _(msg: Bot.MessageSession, apilink: str):
    t = WikiLogUtil(msg)
    infos = json.loads(t.query.infos)
    wiki_info = WikiLib(apilink)
    status = await wiki_info.check_wiki_available()
    if status.value.api in infos:
        t.set_use_bot(status.value.api, 'enable' in msg.parsed_msg)
    else:
        await msg.finish(msg.locale.t('wikilog.message.use_bot.invalid_apilink'))


@wikilog.handle('rcshow set <apilink> ...')
async def _(msg: Bot.MessageSession, apilink: str):
    rcshows = msg.parsed_msg.get('...')
    if rcshows:
        t = WikiLogUtil(msg)
        infos = json.loads(t.query.infos)
        wiki_info = WikiLib(apilink)
        status = await wiki_info.check_wiki_available()
        if status.value.api in infos:
            t.set_rcshow(status.value.api, rcshows)
            await msg.finish(msg.locale.t('wikilog.message.rcshow_set.success'))
        else:
            await msg.finish(msg.locale.t('wikilog.message.rcshow_set.invalid_apilink'))
    else:
        await msg.finish(msg.locale.t('wikilog.message.rcshow_set.no_rcshow'))


@wikilog.handle('list')
async def list_wiki_link(msg: Bot.MessageSession):
    t = WikiLogUtil(msg)
    infos = json.loads(t.query.infos)
    text = ''
    for apilink in infos:
        text += f'{apilink}: \n'
        text += 'AbuseLog: ' + ('Enabled' if infos[apilink]['AbuseLog']['enable'] else 'Disabled') + '\n'
        text += 'Filters: ' + '"' + '" "'.join(infos[apilink]['AbuseLog']['filters']) + '"' + '\n'
        text += 'RecentChanges: ' + ('Enabled' if infos[apilink]['RecentChanges']['enable'] else 'Disabled') + '\n'
        text += 'Filters: ' + '"' + '" "'.join(infos[apilink]['RecentChanges']['filters']) + '"' + '\n'
        text += 'RCShow: ' + '"' + '" "'.join(infos[apilink]['RecentChanges']['rcshow']) + '"' + '\n'
        text += 'UseBot: ' + ('Enabled' if infos[apilink]['use_bot'] else 'Disabled') + '\n'
    await msg.finish(text)



@wikilog.hook('matched')
async def _(fetch: Bot.FetchTarget, ctx: Bot.ModuleHookContext):
    matched = ctx.args['matched_logs']
    Logger.debug('Received matched_logs hook: ' + str(matched))
    for id_ in matched:
        Logger.debug(id_)
        ft = await fetch.fetch_target(id_)
        Logger.debug(ft)
        if ft:
            for wiki in matched[id_]:
                wiki_info = (await WikiLib(wiki).check_wiki_available()).value

                if matched[id_][wiki]['AbuseLog']:
                    for log in matched[id_][wiki]['AbuseLog']:
                        send_msg = []
                        s = f'用户：{log["user"]}\n' \
                            f'页面标题：{log["title"]}\n' \
                            f'过滤器名：{log["filter"]}\n' \
                            f'操作：{log["action"]}\n'
                        result = log['result']
                        if not result:
                            result = 'pass'
                        s += '处理结果：' + result

                        chk = await dirty_check(s)
                        for z in chk:
                            sz = z['content']
                            send_msg.append(sz)
                            send_msg.append(FormattedTime(strptime2ts(log['timestamp'])))
                            if not z['status']:
                                send_msg.append('\n检测到特定文字被屏蔽，请前往日志查看所有消息。\n' +
                                                wiki_info.articlepath.replace('$1', 'Special:AbuseLog'))
                            await ft.send_direct_message(send_msg)
                if matched[id_][wiki]['RecentChanges']:
                    rc = await convert_rc_to_detailed_format(matched[id_][wiki]['RecentChanges'], wiki_info, ft.parent)
                    for x in rc:
                        await ft.send_direct_message(x)
