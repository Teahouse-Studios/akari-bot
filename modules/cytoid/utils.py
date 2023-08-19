import ujson as json

from core.utils.http import get_url


async def get_profile_name(userid):
    try:
        profile_url = 'http://services.cytoid.io/profile/' + userid
        profile = json.loads(await get_url(profile_url, 200))
    except:
        return False
    uid = profile['user']['uid']
    nick = profile['user']['name']
    if nick is None:
        nick = False

    return uid, nick
