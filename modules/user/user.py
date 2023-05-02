import os
import re
import shutil
import traceback
import urllib.parse

from bs4 import BeautifulSoup as bs

from core.builtins import Plain, Image
from core.utils.http import get_url, download_to_cache
from modules.wiki.utils.UTC8 import UTC8
from modules.wiki.utils.wikilib import WikiLib
from .tpg import tpg


async def get_user_info(wikiurl, username, pic=False):
    wiki = WikiLib(wikiurl)
    if not await wiki.check_wiki_available():
        return [Plain(f'{wikiurl}不可用。')]
    await wiki.fixup_wiki_info()
    match_interwiki = re.match(r'(.*?):(.*)', username)
    if match_interwiki:
        if match_interwiki.group(1) in wiki.wiki_info.interwiki:
            return await get_user_info(wiki.wiki_info.interwiki[match_interwiki.group(1)], match_interwiki.group(2),
                                       pic)
    data = {}
    base_user_info = (await wiki.get_json(action='query', list='users', ususers=username,
                                          usprop='groups|blockinfo|registration|editcount|gender'))['query']['users'][0]
    if 'missing' in base_user_info:
        return [Plain('没有找到此用户。')]
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
    data['registration_time'] = UTC8(data['registration_time'], 'full') if data[
        'registration_time'] is not None else '未知'
    data['edited_count'] = str(base_user_info['editcount'])
    data['gender'] = base_user_info['gender']
    if data['gender'] == 'female':
        data['gender'] = '女'
    elif data['gender'] == 'male':
        data['gender'] = '男'
    elif data['gender'] == 'unknown':
        data['gender'] = '未知'
    # if one day LGBTers...

    try:
        gp_clawler = bs(await get_url(re.sub(r'\$1', 'UserProfile: ' + username, wiki.wiki_info.articlepath), 200),
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
    except Exception:
        traceback.print_exc()
    if 'blockedby' in base_user_info:
        data['blocked_by'] = base_user_info['blockedby']
        data['blocked_time'] = base_user_info['blockedtimestamp']
        data['blocked_time'] = UTC8(data['blocked_time'], 'full') if data['blocked_time'] is not None else '未知'
        data['blocked_expires'] = base_user_info['blockedexpiry']
        data['blocked_expires'] = UTC8(data['blocked_expires'], 'full') if data['blocked_expires'] is not None else '未知'
        data['blocked_reason'] = base_user_info['blockedreason']
        data['blocked_reason'] = data['blocked_reason'] if data['blocked_reason'] is not None else '未知'

    if pic:
        assets_path = os.path.abspath('./assets/')
        icon_path = os.path.join(assets_path, 'favicon')
        if not os.path.exists(icon_path):
            os.makedirs(icon_path)
        site_icon = os.path.join(icon_path, urllib.parse.urlparse(wiki.wiki_info.api).netloc)
        if not os.path.exists(site_icon):
            os.makedirs(site_icon)
        if 'Wiki.png' not in os.listdir(site_icon):
            query_wiki = await wiki.parse_page_info('File:Wiki.png')
            file = query_wiki.file
            get_file = await download_to_cache(file)
            shutil.copy(get_file, os.path.join(site_icon, 'Wiki.png'))
        bantype = None
        blocked_by = data.get('blocked_by', False)
        blocked_reason = data.get('blocked_reason', False)
        if blocked_by and not blocked_reason:
            bantype = 'YN'
        elif blocked_by and blocked_reason:
            bantype = 'Y'
        image = tpg(
            favicon=os.path.join(site_icon, 'Wiki.png'),
            wikiname=wiki.wiki_info.name,
            username=data['username'] if 'username' in data else '?',
            gender=data['gender'] if 'gender' in data else '?',
            registertime=data['registration_time'] if 'registration_time' in data else '?',
            contributionwikis=data['edited_wiki_count'] if 'edited_wiki_count' in data else '?',
            createcount=data['created_page_count'] if 'created_page_count' in data else '?',
            editcount=data['edited_count'] if 'edited_count' in data else '?',
            deletecount=data['deleted_count'] if 'deleted_count' in data else '?',
            patrolcount=data['patrolled_count'] if 'patrolled_count' in data else '?',
            sitetop=data['site_rank'] if 'site_rank' in data else '?',
            globaltop=data['global_rank'] if 'global_rank' in data else '?',
            wikipoint=data['wikipoints'] if 'wikipoints' in data else '?',
            blockbyuser=data['blocked_by'] if 'blocked_by' in data else '?',
            blocktimestamp1=data['blocked_time'] if 'blocked_time' in data else '?',
            blocktimestamp2=data['blocked_expires'] if 'blocked_expires' in data else '?',
            blockreason=data['blocked_reason'] if 'blocked_reason' in data else '?',
            bantype=bantype)
        return [Plain(data['url']), Image(image)]

    else:
        msgs = []
        if user := data.get('username', False):
            msgs.append('用户：' + user + (' | 编辑数：' + data['edited_count']
                                        if 'edited_count' in data and 'created_page_count' not in data else ''))
        if users_groups := data.get('users_groups', False):
            msgs.append('用户组：' + '、'.join(users_groups))
        if gender_ := data.get('gender', False):
            msgs.append('性别：' + gender_)
        if registration := data.get('registration_time', False):
            msgs.append('注册时间：' + registration)
        if edited_wiki_count := data.get('edited_wiki_count', False):
            msgs.append('编辑过的Wiki：' + edited_wiki_count)

        sub_edit_counts1 = []
        if created_page_count := data.get('created_page_count', False):
            sub_edit_counts1.append('创建数：' + created_page_count)
        if edited_count := data.get('edited_count', False) and created_page_count:
            sub_edit_counts1.append('编辑数：' + edited_count)
        sub_edit_counts2 = []
        if deleted_count := data.get('deleted_count', False):
            sub_edit_counts2.append('删除数：' + deleted_count)
        if patrolled_count := data.get('patrolled_count', False):
            sub_edit_counts2.append('巡查数：' + patrolled_count)
        sub_edit_counts3 = []
        if site_rank := data.get('site_rank', False):
            sub_edit_counts3.append('本站排名：' + site_rank)
        if global_rank := data.get('global_rank', False):
            sub_edit_counts3.append('全站排名：' + global_rank)
        sub_edit_counts4 = []
        if friends_count := data.get('friends_count', False):
            sub_edit_counts4.append('好友数：' + friends_count)
        if wikipoints := data.get('wikipoints', False):
            sub_edit_counts4.append('Wikipoints：' + wikipoints)
        if sub_edit_counts1:
            msgs.append(' | '.join(sub_edit_counts1))
        if sub_edit_counts2:
            msgs.append(' | '.join(sub_edit_counts2))
        if sub_edit_counts3:
            msgs.append(' | '.join(sub_edit_counts3))
        if sub_edit_counts4:
            msgs.append(' | '.join(sub_edit_counts4))

        if global_users_groups := data.get('global_users_groups', False):
            msgs.append('全域用户组：' + '、'.join(global_users_groups))
        if global_edit_count := data.get('global_edit_count', False):
            msgs.append('全域编辑数：' + global_edit_count)
        if global_home := data.get('global_home', False):
            msgs.append('注册Wiki：' + global_home)

        if blocked_by := data.get('blocked_by', False):
            msgs.append(data['user'] + '正在被封禁中！')
            msgs.append(
                '被' + blocked_by + '封禁，' + ('时间从' + data['blocked_time'] if 'blocked_time' in data else '')
                + ('到' + data['blocked_expires'] if 'blocked_expires' in data else '')
                + ('，理由：' + data['blocked_reason'] if 'blocked_reason' in data else ''))

        if url := data.get('url', False):
            msgs.append(url)

        if msgs:
            return [Plain('\n'.join(msgs))]
