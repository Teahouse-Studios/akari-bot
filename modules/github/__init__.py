import re
import aiohttp
import traceback
import datetime

from core.template import sendMessage
from core.dirty_check import check

from graia.application import MessageChain
from graia.application.message.elements.internal import Plain

async def time_diff(time: str):
    datetimed = datetime.datetime.strftime(time, '%Y-%m-%dT%H:%M:%SZ')
    now = datetime.datetime.now()
    diff = now - datetimed

    if diff.year > 0:
        return diff.year + ' year(s)'
    if diff.month > 0:
        return diff.month + ' month(s)'
    if diff.day > 0:
        return diff.day + ' day(s)'
    if diff.hour > 0:
        return diff.hour + ' hour(s)'
    if diff.minute > 0:
        return diff.hour + ' minute(s)'
    if diff.second > 0:
        return diff.second + ' second(s)'
    else:
        return 'miliseconds'    

async def dirty_check(self, text):
    if not self.danger_wiki_check():
        return False
    check = await check([text])
    print(check)
    if check.find('<吃掉了>') != -1 or check.find('<全部吃掉了>') != -1:
        return True
    return False

async def query(url: str, format: str):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as req:
                if hasattr(req, format):
                    return await getattr(req, format)()
                else:
                    raise ValueError(f"NoSuchMethod: {format}")
        except Exception:
            traceback.print_exc()
            return False

async def repo(kwargs: dict, cmd: list):
    obj = cmd[1].replace('@', '')
    result = await query('https://api.github.com/repos/' + obj, 'json')
    name = result['full_name']
    url = result['html_url']
    id = result['id']
    desc = result['description']
    lang = result['language']
    fork = result['forks_count']
    star = result['stargazers_count']
    watch = result['watchers_count']
    mirror = result['mirror_url']
    license = result['license']['spdx_id']
    is_fork = result['fork']
    created = result['created_at']
    updated = result['updated_at']

    if mirror:
        mirror = f' (This is a mirror of {mirror} )'

    if is_fork:
        parent_name = result['parent']['name']
        parent = f' (This is a mirror of {parent_name} )'

    msg = f'''{name} ({id})
{desc}

Language · {lang} | Fork · {fork} | Star · {star} | Watch · {watch}
License: {license}
Created {time_diff(created)} ago | Updated {time_diff(updated)} ago

{url}{mirror}{parent}
'''

    is_dirty = await dirty_check(msg)
    if is_dirty:
        msg = 'https://wdf.ink/6OUp'

    await sendMessage(kwargs, MessageChain.create([Plain(msg)]))

async def user(kwargs: dict, cmd: list):
    obj = cmd[1]
    result = await query('https://api.github.com/users/' + obj, 'json')
    login = result['login']
    name = result['name']
    id = result['id']
    url = result['html_url']
    bio = result['bio']
    type = result['type']
    company = result['company']
    following = result['following']
    follower = result['followers']
    repo = result['public_repos']
    gist = result['public_gists']
    is_staff = result['license']['spdx_id']
    twitter = result['twitter_username']
    created = result['created_at']
    updated = result['updated_at']
    website = result['blog']
    location = result['location']
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

    optional_text = '\n' + optional.join(' | ')
    msg = f'''{login} aka {name} ({id})
{bio}

Type · {type} | Follower · {follower} | Following · {following} | Repo · {repo} | Gist · {gist}{optional_text}
Account Created {time_diff(created)} ago | Latest activity {time_diff(updated)} ago

{url}
'''

    is_dirty = await dirty_check(msg)
    if is_dirty:
        msg = 'https://wdf.ink/6OUp'

    await sendMessage(kwargs, MessageChain.create([Plain(msg)]))

async def forker(kwargs: dict):
    cmd = kwargs['trigger_msg']
    cmd = re.sub(r'^github ', '', cmd)
    if cmd[0] == 'repo':
        return repo(kwargs ,cmd)
    elif cmd[0] == 'user' or cmd[0] == 'usr' or cmd[0] == 'organization' or cmd[0] == 'org':
        return user(kwargs, cmd)

command = {'github': forker}
help = {'github':{'github': '''- ~github repo <user>/<name>：获取GitHub仓库信息
- ~github <user|usr|organization|org>：获取GitHub用户或组织信息'''}}
