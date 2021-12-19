import traceback

from core.elements import MessageSession
from core.utils.bot import get_url
from modules.github.utils import time_diff, dirty_check, darkCheck


async def user(msg: MessageSession):
    try:
        result = await get_url('https://api.github.com/users/' + msg.parsed_msg['<name>'], fmt='json')
        optional = []
        if 'hireable' in result and result['hireable'] is True:
            optional.append('Hireable')
        if 'is_staff' in result and result['is_staff'] is True:
            optional.append('GitHub Staff')
        if 'company' in result and result['company'] is not None:
            optional.append('Work · ' + result['company'])
        if 'twitter_username' in result and result['twitter_username'] is not None:
            optional.append('Twitter · ' + result['twitter_username'])
        if 'blog' in result and result['blog'] is not None:
            optional.append('Site · ' + result['blog'])
        if 'location' in result and result['location'] is not None:
            optional.append('Location · ' + result['location'])

        bio = result['bio']
        if bio is None:
            bio = ''
        else:
            bio = '\n' + result['bio']

        optional_text = '\n' + ' | '.join(optional)
        message = f'''{result['login']} aka {result['name']} ({result['id']}){bio}

Type · {result['type']} | Follower · {result['followers']} | Following · {result['following']} | Repo · {result['public_repos']} | Gist · {result['public_gists']}{optional_text}
Account Created {time_diff(result['created_at'])} ago | Latest activity {time_diff(result['updated_at'])} ago

{result['html_url']}'''

        is_dirty = await dirty_check(message, result['login']) or darkCheck(message)
        if is_dirty:
            message = 'https://wdf.ink/6OUp'

        await msg.sendMessage(message)
    except Exception as error:
        if result['message'] == 'Not Found':
            await msg.sendMessage('发生错误：查无此人，请检查拼写是否正确。')
        else:
            await msg.sendMessage('发生错误：' + str(
                error) + '\n错误汇报地址：https://github.com/Teahouse-Studios/bot/issues/new?assignees=OasisAkari&labels=bug&template=report_bug.yaml&title=%5BBUG%5D%3A+')
            traceback.print_exc()
