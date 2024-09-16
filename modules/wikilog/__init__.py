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


def compare_groups(old_groups, new_groups):
    added_groups = [group for group in new_groups if group not in old_groups]
    removed_groups = [group for group in old_groups if group not in new_groups]
    added = "+" + ", ".join(map(str, added_groups)) if added_groups else ""
    removed = "-" + ", ".join(map(str, removed_groups)) if removed_groups else ""
    return f"{added} {removed}" if added and removed else f"{added}{removed}"


async def convert_rc(rc: list, wiki_info: WikiInfo, msg: Bot.MessageSession):
    rclist = []
    userlist = []
    titlelist = []
    commentlist = []
    for x in rc:
        if 'title' in x:
            userlist.append(x.get('user', ''))
            titlelist.append(x.get('title'))
            commentlist.append(x.get('comment', ''))
    Logger.debug(userlist)
    userlist = list(set(userlist))
    titlelist = list(set(titlelist))
    commentlist = list(set(commentlist))
    checked_userlist = await dirty_check(*userlist)
    user_checked_map = {}
    for u in checked_userlist:
        user_checked = u['content']
        if user_checked.find("<吃掉了>") != -1 or user_checked.find("<全部吃掉了>") != -1:
            user_checked = user_checked.replace("<吃掉了>", msg.locale.t("check.redacted"))
            user_checked = user_checked.replace("<全部吃掉了>", msg.locale.t("check.redacted.all"))
        user_checked_map[u['original']] = user_checked
    checked_titlelist = await dirty_check(*titlelist)
    title_checked_map = {}
    for t in checked_titlelist:
        title_checked = t['content']
        if title_checked.find("<吃掉了>") != -1 or title_checked.find("<全部吃掉了>") != -1:
            title_checked = title_checked.replace("<吃掉了>", msg.locale.t("check.redacted"))
            title_checked = title_checked.replace("<全部吃掉了>", msg.locale.t("check.redacted.all"))
        title_checked_map[t['original']] = title_checked
    checked_commentlist = await dirty_check(*commentlist)
    comment_checked_map = {}
    for c in checked_commentlist:
        comment_checked = c['content']
        if comment_checked.find("<吃掉了>") != -1 or comment_checked.find("<全部吃掉了>") != -1:
            comment_checked = comment_checked.replace("<吃掉了>", msg.locale.t("check.redacted"))
            comment_checked = comment_checked.replace("<全部吃掉了>", msg.locale.t("check.redacted.all"))
        comment_checked_map[c['original']] = comment_checked
    for x in rc:
        if 'title' in x:
            t = []
            user = user_checked_map[x['user']]
            title = title_checked_map[x['title']]
            comment = comment_checked_map[x['comment']] if x.get('comment') else None

            time = msg.ts2strftime(strptime2ts(x['timestamp']), iso=True)
            t.append(time)
            if x['type'] == 'edit':
                count = x['newlen'] - x['oldlen']
                if count > 0:
                    count = f'+{str(count)}'
                else:
                    count = str(count)
                t.append(f"{title} .. ({count}) .. {user}")
                if comment:
                    t.append(comment)
                t.append(
                    wiki_info.articlepath.replace(
                        '$1',
                        f"{urllib.parse.quote(title)}?oldid={x['old_revid']}&diff={x['revid']}"))
            if x['type'] == 'new':
                r = msg.locale.t('message.brackets', msg=msg.locale.t(
                    'wiki.message.rc.new_redirect')) if 'redirect' in x else ''
                t.append(f"{title}{r} .. (+{x['newlen']}) .. {user}")
                if comment:
                    t.append(comment)
            if x['type'] == 'log':
                if x['logtype'] == x['logaction']:
                    log = msg.locale.t(f"wiki.message.rc.action.{x['logtype']}", user=user, title=title)
                else:
                    log = msg.locale.t(
                        f"wiki.message.rc.action.{
                            x['logtype']}.{
                            x['logaction']}",
                        user=user,
                        title=title)
                if log.find("{") != -1 and log.find("}") != -1:
                    if x['logtype'] == x['logaction']:
                        log = f"{user} {x['logtype']} {title}"
                    else:
                        log = f"{user} {x['logaction']} {x['logtype']} {title}"
                t.append(log)
                params = x['logparams']
                if 'suppressredirect' in params:
                    t.append(msg.locale.t('wiki.message.rc.params.suppress_redirect'))
                if 'oldgroups' and 'newgroups' in params:
                    t.append(compare_groups(params['oldgroups'], params['newgroups']))
                if 'oldmodel' and 'newmodel' in params:
                    t.append(f"{params['oldmodel']} -> {params['newmodel']}")
                if 'description' in params:
                    t.append(params['description'])
                if 'duration' in params:
                    t.append(msg.locale.t('wiki.message.rc.params.duration') + params['duration'])
                if 'flags' in params:
                    t.append(', '.join(params['flags']))
                if 'tag' in params:
                    t.append(msg.locale.t('wiki.message.rc.params.tag') + params['tag'])
                if 'target_title' in params:
                    t.append(msg.locale.t('wiki.message.rc.params.target_title') + params['target_title'])
                if comment:
                    t.append(comment)
                if x['revid'] != 0:
                    t.append(wiki_info.articlepath.replace(
                        "$1", f"{urllib.parse.quote(title_checked_map[x['title']])}"))
            rclist.append('\n'.join(t))
    return rclist


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
                    rc = await convert_rc(matched[id_][wiki]['RecentChanges'], wiki_info, ft.parent)
                    for x in rc:
                        await ft.send_direct_message(x)
