eback

from core.builtins import Url, Bot
from core.dirty_check import rickroll
from core.utils.http import get_url
from modules.github.utils import time_diff, dirty_check, darkCheck


async def user(msg: Bot.MessageSession):
    try:
        result = await get_url('https://api.github.com/users/' + msg.parsed_msg['<name>'], 200, fmt='json')
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

{str(Url(result['html_url']))}'''

        is_dirty = await dirty_check(message, result['login']) or darkCheck(message)
        if is_dirty:
            await msg.finish(rickroll(msg))

        await msg.finish(message)
    except ValueError as e:
        if str(e).startswith('404'):
            await msg.finish(msg.locale.t("github.message.repo.not_found"))
        traceback.print_exc()
