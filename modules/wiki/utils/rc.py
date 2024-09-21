import urllib.parse

from core.builtins import Url, Bot
from core.dirty_check import check
from core.logger import Logger
from modules.wiki.utils.time import strptime2ts
from modules.wiki.utils.wikilib import WikiLib, WikiInfo


async def rc(msg: Bot.MessageSession, wiki_url):
    wiki = WikiLib(wiki_url)
    query = await wiki.get_json(action='query', list='recentchanges',
                                rcprop='title|user|timestamp|loginfo|comment|sizes',
                                rclimit=10,
                                rctype='edit|new|log',
                                _no_login=not msg.options.get("use_bot_account", False))
    pageurl = wiki.wiki_info.articlepath.replace('$1', 'Special:RecentChanges')
    d = []
    for x in query['query']['recentchanges']:
        if 'title' in x:
            if x['type'] in ['edit', 'new']:
                count = x['newlen'] - x['oldlen']
                if count > 0:
                    count = f'+{str(count)}'
                else:
                    count = str(count)
                d.append(f"•{msg.ts2strftime(strptime2ts(x['timestamp']), iso=True,
                                             timezone=False)} - {x['title']} .. ({count}) .. {x['user']}")
                if x['comment']:
                    comment = msg.locale.t('message.brackets', msg=x['comment'])
                    d.append(comment)
            if x['type'] == 'log':
                if x['logtype'] == x['logaction']:
                    log = msg.locale.t(f"wiki.message.rc.action.{x['logtype']}", user=x['user'], title=x['title'])
                else:
                    log = msg.locale.t(
                        f"wiki.message.rc.action.{
                            x['logtype']}.{
                            x['logaction']}",
                        user=x['user'],
                        title=x['title'])
                if log.find("{") != -1 and log.find("}") != -1:
                    if x['logaction'] == x['logtype']:
                        log = f"{x['user']} {x['logtype']} {x['title']}"
                    else:
                        log = f"{x['user']} {x['logaction']} {x['logtype']} {x['title']}"
                d.append(f"•{msg.ts2strftime(strptime2ts(x['timestamp']), iso=True, timezone=False)} - {log}")
                params = x['logparams']
                if 'suppressredirect' in params:
                    d.append(msg.locale.t('wiki.message.rc.params.suppress_redirect'))
                if 'oldgroups' and 'newgroups' in params:
                    d.append(compare_groups(params['oldgroups'], params['newgroups']))
                if 'oldmodel' and 'newmodel' in params:
                    d.append(f"{params['oldmodel']} -> {params['newmodel']}")
                if 'description' in params:
                    d.append(params['description'])
                if 'duration' in params:
                    d.append(msg.locale.t('wiki.message.rc.params.duration') + params['duration'])
                if 'flags' in params:
                    d.append(', '.join(params['flags']))
                if 'tag' in params:
                    d.append(msg.locale.t('wiki.message.rc.params.tag') + params['tag'])
                if 'target_title' in params:
                    d.append(msg.locale.t('wiki.message.rc.params.target_title') + params['target_title'])
                if x['comment']:
                    comment = msg.locale.t('message.brackets', msg=x['comment'])
                    d.append(comment)
    y = await check(*d)
    y = '\n'.join(z['content'] for z in y)
    if y.find("<吃掉了>") != -1 or y.find("<全部吃掉了>") != -1:
        y = y.replace("<吃掉了>", msg.locale.t("check.redacted"))
        y = y.replace("<全部吃掉了>", msg.locale.t("check.redacted.all"))
        return f'{str(Url(pageurl))}\n{y}\n{msg.locale.t("message.collapse", amount="10")}\n{
            msg.locale.t("wiki.message.utils.redacted")}'
    else:
        return f'{str(Url(pageurl))}\n{y}\n{msg.locale.t("message.collapse", amount="10")}'


def compare_groups(old_groups, new_groups):
    added_groups = [group for group in new_groups if group not in old_groups]
    removed_groups = [group for group in old_groups if group not in new_groups]
    added = "+" + ",".join(map(str, added_groups)) if added_groups else ""
    removed = "-" + ",".join(map(str, removed_groups)) if removed_groups else ""
    return f"{added} {removed}" if added and removed else f"{added}{removed}"


async def convert_rc_to_detailed_format(rc: list, wiki_info: WikiInfo, msg: Bot.MessageSession):
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
    checked_userlist = await check(*userlist)
    user_checked_map = {}
    for u in checked_userlist:
        user_checked = u['content']
        if user_checked.find("<吃掉了>") != -1 or user_checked.find("<全部吃掉了>") != -1:
            user_checked = user_checked.replace("<吃掉了>", msg.locale.t(
                "check.redacted") + '\n' + wiki_info.articlepath.replace('$1', "Special:RecentChanges"))
            user_checked = user_checked.replace("<全部吃掉了>", msg.locale.t(
                "check.redacted.all") + '\n' + wiki_info.articlepath.replace('$1', "Special:RecentChanges"))
        user_checked_map[u['original']] = user_checked
    checked_titlelist = await check(*titlelist)
    title_checked_map = {}
    for t in checked_titlelist:
        title_checked = t['content']
        if title_checked.find("<吃掉了>") != -1 or title_checked.find("<全部吃掉了>") != -1:
            title_checked = title_checked.replace("<吃掉了>", msg.locale.t(
                "check.redacted") + '\n' + wiki_info.articlepath.replace('$1', "Special:RecentChanges"))
            title_checked = title_checked.replace("<全部吃掉了>", msg.locale.t(
                "check.redacted.all") + '\n' + wiki_info.articlepath.replace('$1', "Special:RecentChanges"))
        title_checked_map[t['original']] = title_checked
    checked_commentlist = await check(*commentlist)
    comment_checked_map = {}
    for c in checked_commentlist:
        comment_checked = c['content']
        if comment_checked.find("<吃掉了>") != -1 or comment_checked.find("<全部吃掉了>") != -1:
            comment_checked = comment_checked.replace("<吃掉了>", msg.locale.t(
                "check.redacted") + '\n' + wiki_info.articlepath.replace('$1', "Special:RecentChanges"))
            comment_checked = comment_checked.replace("<全部吃掉了>", msg.locale.t(
                "check.redacted.all") + '\n' + wiki_info.articlepath.replace('$1', "Special:RecentChanges"))
        comment_checked_map[c['original']] = comment_checked
    for x in rc:
        if 'title' in x:
            t = []
            user = user_checked_map[x['user']]
            title = title_checked_map[x['title']]
            comment = comment_checked_map[x['comment']] if x.get('comment') else None

            if x['type'] in ['edit', 'categorize']:
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
            time = msg.ts2strftime(strptime2ts(x['timestamp']), iso=True)
            t.append(time)
            rclist.append('\n'.join(t))
    return rclist
