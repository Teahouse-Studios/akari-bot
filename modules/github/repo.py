import traceback

from core.builtins.message import MessageSession
from core.elements import Image, Plain, Url
from core.elements.others import ErrorMessage
from core.utils import get_url
from modules.github.utils import time_diff, dirty_check, darkCheck


async def repo(msg: MessageSession):
    try:
        result = await get_url('https://api.github.com/repos/' + msg.parsed_msg['<name>'], fmt='json')
        if 'message' in result and result['message'] == 'Not Found':
            raise RuntimeError('此仓库不存在。')
        elif 'message' in result and result['message']:
            raise RuntimeError(result['message'])
        rlicense = 'Unknown'
        if 'license' in result and result['license'] is not None:
            if 'spdx_id' in result['license']:
                rlicense = result['license']['spdx_id']
        is_fork = result['fork']
        parent = False

        if result['homepage'] is not None:
            website = 'Website: ' + str(Url(result['homepage'])) + '\n'
        else:
            website = ''

        if result['mirror_url'] is not None:
            mirror = f' (This is a mirror of {str(Url(result["mirror_url"]))} )'
        else:
            mirror = ''

        if is_fork:
            parent_name = result['parent']['name']
            parent = f' (This is a fork of {parent_name} )'

        desc = result['description']
        if desc is None:
            desc = ''
        else:
            desc = '\n' + result['description']

        message = f'''{result['full_name']} ({result['id']}){desc}

Language · {result['language']} | Fork · {result['forks_count']} | Star · {result['stargazers_count']} | Watch · {result['watchers_count']}
License: {rlicense}
Created {time_diff(result['created_at'])} ago | Updated {time_diff(result['updated_at'])} ago

{website}{str(Url(result['html_url']))}'''

        if mirror:
            message += '\n' + mirror

        if parent:
            message += '\n' + parent

        is_dirty = await dirty_check(message, result['owner']['login']) or darkCheck(message)
        if is_dirty:
            message = 'https://wdf.ink/6OUp'
            await msg.finish([Plain(message)])
        else:
            await msg.finish([Plain(message), Image(
                path=f'https://opengraph.githubassets.com/c9f4179f4d560950b2355c82aa2b7750bffd945744f9b8ea3f93cc24779745a0/{result["full_name"]}')])
    except Exception as e:
        if result['message'] == 'Not Found':
            await msg.finish('发生错误：查无此人，请检查拼写是否正确。')
        else:
            await msg.sendMessage(ErrorMessage(str(e)))
            traceback.print_exc()
