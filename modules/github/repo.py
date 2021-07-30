import traceback

from core.elements import MessageSession, Image, Plain

from modules.github.utils import query, time_diff, dirty_check, darkCheck

async def repo(msg: MessageSession):
    try:
        result = await query('https://api.github.com/repos/' + msg.parsed_msg['name'], 'json')
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
            website = 'Website: ' + result['homepage'] + '\n'
        else:
            website = ''

        if result['mirror_url'] is not None:
            mirror = f' (This is a mirror of {result["mirror_url"]} )'
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

        msg = f'''{result['full_name']} ({result['id']}){desc}

Language · {result['language']} | Fork · {result['forks_count']} | Star · {result['stargazers_count']} | Watch · {result['watchers_count']}
License: {rlicense}
Created {time_diff(result['created_at'])} ago | Updated {time_diff(result['updated_at'])} ago

{website}{result['html_url']}'''

        if mirror:
            msg += '\n' + mirror

        if parent:
            msg += '\n' + parent

        is_dirty = await dirty_check(msg, result['owner']['login']) or darkCheck(msg)
        if is_dirty:
            msg = 'https://wdf.ink/6OUp'
            await msg.sendMessage([Plain(msg)])
        else:
            await msg.sendMessage([Plain(msg), Image.fromNetworkAddress(f'https://opengraph.githubassets.com/c9f4179f4d560950b2355c82aa2b7750bffd945744f9b8ea3f93cc24779745a0/{result["full_name"]}')])
    except Exception as e:
        await msg.sendMessage('发生错误：' + str(e))
        traceback.print_exc()
