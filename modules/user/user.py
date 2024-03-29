import re
import traceback
import urllib.parse

from bs4 import BeautifulSoup as bs

from core.builtins import Bot, Plain
from core.dirty_check import check_bool, rickroll
from core.logger import Logger
from core.utils.http import get_url
from modules.wiki.utils.wikilib import WikiLib
from modules.wiki.utils.time import strptime2ts


async def get_user_info(msg: Bot.MessageSession, wikiurl, username, profile=False):
    wiki = WikiLib(wikiurl)
    if not await wiki.check_wiki_available():
        await msg.finish(msg.locale.t('user.message.wiki_unavailable', wikiurl=wikiurl))
    await wiki.fixup_wiki_info()
    match_interwiki = re.match(r'(.*?):(.*)', username)
    if match_interwiki:
        if match_interwiki.group(1) in wiki.wiki_info.interwiki:
            await get_user_info(msg, wiki.wiki_info.interwiki[match_interwiki.group(1)],
                                       match_interwiki.group(2), profile)
    data = {}
    base_user_info = (await wiki.get_json(action='query', list='users', ususers=username,
                                          usprop='groups|blockinfo|registration|editcount|gender'))['query']['users'][0]
    if 'missing' in base_user_info:
        return [Plain(msg.locale.t('user.message.not_found'))]
    data['username'] = base_user_info['name']
    data['url'] = re.sub(r'\$1', urllib.parse.quote('User:' + username), wiki.wiki_info.articlepath)
    groups = {}
    get_groups = await wiki.get_json(action='query', meta='allmessages', amprefix='group-')
    for a in get_groups['query']['allmessages']:
        groups[re.sub('^group-', '', a['name'])] = a['*']
    user_central_auth_data = {}
    if 'CentralAuth' in wiki.wiki_info.extensions:
        user_central_auth_data = await wiki.get_json(action='query', meta='globaluserinfo', guiuser=username,
                                                     guiprop='editcount|groups')
    data['users_groups'] = []
    users_groups_ = base_user_info['groups']
    for x in users_groups_:
        if x != '*':
            data['users_groups'].append(groups[x] if x in groups else x)
    data['global_users_groups'] = []
    if user_central_auth_data:
        data['global_edit_count'] = str(user_central_auth_data['query']['globaluserinfo']['editcount'])
        data['global_home'] = user_central_auth_data['query']['globaluserinfo']['home']
        for g in user_central_auth_data['query']['globaluserinfo']['groups']:
            data['global_users_groups'].append(groups[g] if g in groups else g)
    data['registration_time'] = base_user_info['registration']
    data['registration_time'] = msg.ts2strftime(strptime2ts(data['registration_time'])) if data[
        'registration_time'] else msg.locale.t(
        'unknown')
    data['edited_count'] = str(base_user_info['editcount'])
    data['gender'] = base_user_info['gender']
    if data['gender'] == 'female':
        data['gender'] = msg.locale.t('user.message.gender.female')
    elif data['gender'] == 'male':
        data['gender'] = msg.locale.t('user.message.gender.male')
    elif data['gender'] == 'unknown':
        data['gender'] = msg.locale.t('unknown')
    # if one day LGBTers...

    if profile:
        try:
            gp_clawler = bs(await get_url(re.sub(r'\$1', 'UserProfile:' + username, wiki.wiki_info.articlepath), 200, logging_err_resp=False),
                            'html.parser')
            dd = gp_clawler.find('div', class_='section stats').find_all('dd')
            data['edited_wiki_count'] = dd[0].text
            data['created_page_count'] = dd[1].text
            data['edited_count'] = dd[2].text
            data['deleted_count'] = dd[3].text
            data['patrolled_count'] = dd[4].text
            data['site_rank'] = dd[5].text
            data['global_rank'] = dd[6].text
            data['friends_count'] = dd[7].text
            data['wikipoints'] = gp_clawler.find('div', class_='score').text
            data['url'] = re.sub(r'\$1', urllib.parse.quote('UserProfile:' + username), wiki.wiki_info.articlepath)
        except ValueError:
            pass
    if 'blockedby' in base_user_info:
        data['blocked_by'] = base_user_info['blockedby']
        data['blocked_time'] = base_user_info['blockedtimestamp']
        if data['blocked_time'] in ['infinity', 'infinite']:
            data['blocked_time'] = msg.locale.t('user.message.blocked.time.infinity')
        else:
            data['blocked_time'] = msg.ts2strftime(strptime2ts(data['blocked_time'])) \
                if data['blocked_time'] else msg.locale.t(
                'unknown')
        data['blocked_expires'] = base_user_info.get('blockexpiry', None)
        if data['blocked_expires'] in ['infinity', 'infinite']:
            data['blocked_expires'] = msg.locale.t('user.message.blocked.time.infinity')
        else:
            data['blocked_expires'] = msg.ts2strftime(strptime2ts(data['blocked_expires'])) if data[
                'blocked_expires'] else msg.locale.t(
                'unknown')
        data['blocked_reason'] = base_user_info['blockreason']
        data['blocked_reason'] = data['blocked_reason'] if data['blocked_reason'] else msg.locale.t(
            'unknown')

    Logger.debug(str(data))
    msgs = []
    if user := data.get('username', False):
        msgs.append(msg.locale.t('user.message.username') + user + (
            ' | ' + msg.locale.t('user.message.edited_count') + data['edited_count']
            if 'edited_count' in data and 'created_page_count' not in data else ''))
    if users_groups := data.get('users_groups', False):
        msgs.append(
            msg.locale.t('user.message.users_groups') + msg.locale.t('message.delimiter').join(users_groups))
    if gender_ := data.get('gender', False):
        msgs.append(msg.locale.t('user.message.gender') + gender_)
    if registration := data.get('registration_time', False):
        msgs.append(msg.locale.t('user.message.registration_time') + registration)
    if edited_wiki_count := data.get('edited_wiki_count', False):
        msgs.append(msg.locale.t('user.message.edited_wiki_count') + edited_wiki_count)

    sub_edit_counts1 = []
    if created_page_count := data.get('created_page_count', False):
        sub_edit_counts1.append(msg.locale.t('user.message.created_page_count') + created_page_count)
    if edited_count := data.get('edited_count', False) and created_page_count:
        sub_edit_counts1.append(msg.locale.t('user.message.edited_count') + edited_count)
    sub_edit_counts2 = []
    if deleted_count := data.get('deleted_count', False):
        sub_edit_counts2.append(msg.locale.t('user.message.deleted_count') + deleted_count)
    if patrolled_count := data.get('patrolled_count', False):
        sub_edit_counts2.append(msg.locale.t('user.message.patrolled_count') + patrolled_count)
    sub_edit_counts3 = []
    if site_rank := data.get('site_rank', False):
        sub_edit_counts3.append(msg.locale.t('user.message.site_rank') + site_rank)
    if global_rank := data.get('global_rank', False):
        sub_edit_counts3.append(msg.locale.t('user.message.global_rank') + global_rank)
    sub_edit_counts4 = []
    if friends_count := data.get('friends_count', False):
        sub_edit_counts4.append(msg.locale.t('user.message.friends_count') + friends_count)
    if wikipoints := data.get('wikipoints', False):
        sub_edit_counts4.append(msg.locale.t('user.message.wikipoints') + wikipoints)
    if sub_edit_counts1:
        msgs.append(' | '.join(sub_edit_counts1))
    if sub_edit_counts2:
        msgs.append(' | '.join(sub_edit_counts2))
    if sub_edit_counts3:
        msgs.append(' | '.join(sub_edit_counts3))
    if sub_edit_counts4:
        msgs.append(' | '.join(sub_edit_counts4))

    if global_users_groups := data.get('global_users_groups', False):
        msgs.append(msg.locale.t('user.message.global_users_groups') + msg.locale.t('message.delimiter').join(
            global_users_groups))
    if global_edit_count := data.get('global_edit_count', False):
        msgs.append(msg.locale.t('user.message.global_edited_count') + global_edit_count)
    if global_home := data.get('global_home', False):
        msgs.append(msg.locale.t('user.message.global_home') + global_home)

    if blocked_by := data.get('blocked_by', False):
        msgs.append(msg.locale.t('user.message.blocked', user=user))
        msgs.append(msg.locale.t('user.message.blocked.detail',
                                  blocked_by=blocked_by,
                                  blocked_time=data['blocked_time'],
                                  blocked_expires=data['blocked_expires']))
        msgs.append(msg.locale.t('user.message.blocked.reason') + data['blocked_reason'])

    if url := data.get('url', False):
        msgs.append(url)

    res = '\n'.join(msgs)
    if await check_bool(res):
        await msg.finish(rickroll(msg))
    await msg.finish(res)
