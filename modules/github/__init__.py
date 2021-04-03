import datetime
import re
import traceback

import aiohttp
from graia.application import MessageChain
from graia.application.message.elements.internal import Plain

from core import dirty_check as dirty
from core.template import sendMessage


def time_diff(time: str):
    datetimed = datetime.datetime.strptime(time, '%Y-%m-%dT%H:%M:%SZ').timestamp()
    now = datetime.datetime.now().timestamp()
    diff = now - datetimed

    diff = diff
    t = diff / 60 / 60 / 24
    dw = ' day(s)'
    if t < 1:
        t = diff / 60 / 60
        dw = ' hour(s)'
        if t < 1:
            t = diff / 60
            dw = ' minute(s)'
            if t < 1:
                t = diff
                dw = ' second(s)'
    diff = str(int(t)) + dw
    return diff


async def dirty_check(text):
    check = await dirty.check([text])
    print(check)
    if check.find('<吃掉了>') != -1 or check.find('<全部吃掉了>') != -1:
        return True
    return False


async def query(url: str, fmt: str):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as req:
                if hasattr(req, fmt):
                    return await getattr(req, fmt)()
                else:
                    raise ValueError(f"NoSuchMethod: {fmt}")
        except Exception:
            traceback.print_exc()
            return False


async def repo(kwargs: dict, cmd: list):
    try:
        try:
            obj = cmd[1].replace('@', '')
        except IndexError:
            obj = cmd[0].replace('@', '')
        result = await query('https://api.github.com/repos/' + obj, 'json')
        name = result['full_name']
        url = result['html_url']
        rid = result['id']
        lang = result['language']
        fork = result['forks_count']
        star = result['stargazers_count']
        watch = result['watchers_count']
        mirror = result['mirror_url']
        rlicense = 'Unknown'
        if 'license' in result:
            if 'spdx_id' in result['license']:
                rlicense = result['license']['spdx_id']
        is_fork = result['fork']
        created = result['created_at']
        updated = result['updated_at']
        parent = False
        website = result['homepage']

        if website is not None:
            website = 'Website: ' + website + '\n'
        else:
            website = False

        if mirror is not None:
            mirror = f' (This is a mirror of {mirror} )'
        else:
            mirror = False

        if is_fork:
            parent_name = result['parent']['name']
            parent = f' (This is a fork of {parent_name} )'

        desc = result['description']
        if desc is None:
            desc = ''
        else:
            desc = '\n' + result['description']

        msg = f'''{name} ({rid}){desc}

Language · {lang} | Fork · {fork} | Star · {star} | Watch · {watch}
License: {rlicense}
Created {time_diff(created)} ago | Updated {time_diff(updated)} ago

{website}{url}
'''

        if mirror:
            msg += '\n' + mirror

        if parent:
            msg += '\n' + parent

        is_dirty = await dirty_check(msg)
        if is_dirty:
            msg = 'https://wdf.ink/6OUp'

        await sendMessage(kwargs, MessageChain.create([Plain(msg)]))
    except Exception as e:
        await sendMessage(kwargs, '发生错误：' + str(e))


async def user(kwargs: dict, cmd: list):
    try:
        obj = cmd[1]
        result = await query('https://api.github.com/users/' + obj, 'json')
        login = result['login']
        name = result['name']
        uid = result['id']
        url = result['html_url']
        utype = result['type']
        if 'company' in result:
            company = result['company']
        else:
            company = False
        following = result['following']
        follower = result['followers']
        repo = result['public_repos']
        gist = result['public_gists']
        is_staff = False
        if 'license' in result:
            if 'spdx_id' in result['license']:
                is_staff = result['license']['spdx_id']
        if 'twitter_username' in result:
            twitter = result['twitter_username']
        else:
            twitter = False
        created = result['created_at']
        updated = result['updated_at']
        if 'blog' in result:
            website = result['blog']
        else:
            website = False
        if 'location' in result:
            location = result['location']
        else:
            location = False
        hireable = False
        if 'hireable' in result:
            hireable = result['hireable']
        optional = []
        if hireable:
            optional.append('Hireable')
        if is_staff:
            optional.append('GitHub Staff')
        if company:
            optional.append('Work · ' + company)
        if twitter:
            optional.append('Twitter · ' + twitter)
        if website:
            optional.append('Site · ' + website)
        if location:
            optional.append('Location · ' + location)

        bio = result['bio']
        if bio is None:
            bio = ''
        else:
            bio = '\n' + result['bio']

        optional_text = '\n' + ' | '.join(optional)
        msg = f'''{login} aka {name} ({uid}){bio}
    
Type · {utype} | Follower · {follower} | Following · {following} | Repo · {repo} | Gist · {gist}{optional_text}
Account Created {time_diff(created)} ago | Latest activity {time_diff(updated)} ago
    
{url}
'''

        is_dirty = await dirty_check(msg)
        if is_dirty:
            msg = 'https://wdf.ink/6OUp'

        await sendMessage(kwargs, MessageChain.create([Plain(msg)]))
    except Exception as error:
        await sendMessage(kwargs, '发生错误：' + str(error))

async def search(kwargs: dict, cmd: list):
    try:
        obj = cmd[1]
        result = await query('https://api.github.com/search/repositories?q=' + obj, 'json')
        items = result['items']
        item_count_expected = int(result['total_count']) if result['total_count'] < 5 else 5
        items_out = []
        for item in items:
            try:
                items_out.append(str(item['full_name'] + ': ' + item['html_url']))
            except TypeError:
                continue
        footnotes = f"另有 {result['total_count'] - 5} 个结果未显示。" if item_count_expected == 5 else ''
        msg = f"搜索成功：共 {result['total_count']} 个结果。\n" + '\n'.join(items_out[0:item_count_expected]) + f'\n{footnotes}'

        is_dirty = await dirty_check(msg)
        if is_dirty:
            msg = 'https://wdf.ink/6OUp'

        await sendMessage(kwargs, MessageChain.create([Plain(msg)]))
    except Exception as error:
        await sendMessage(kwargs, '发生错误：' + str(error))

async def forker(kwargs: dict):
    cmd = kwargs['trigger_msg']
    cmd = re.sub(r'^github ', '', cmd).split(' ')
    if cmd[0] == 'repo' or '/' in cmd[0]:
        return await repo(kwargs, cmd)
    elif cmd[0] in ['user', 'usr', 'organization', 'org']:
        return await user(kwargs, cmd)
    elif cmd[0] == 'search':
        return await search(kwargs, cmd)
    else:
        return await sendMessage(kwargs, '发生错误：指令使用错误，请选择 repo 或 user 工作模式。使用 ~help github 查看详细帮助。')


command = {'github': forker}
help = {'github':{'module': '查询 Github 的指定 repo（仓库）或用户详情或进行搜索。', 'help': '''~github repo <user>/<name> - 获取 GitHub 仓库信息。
~github <user|usr|organization|org> - 获取 GitHub 用户或组织信息。
~github search - 搜索 GitHub 上的仓库。'''}}
