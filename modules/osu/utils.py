import ujson as json

from config import Config
from core.utils.http import get_url


async def get_profile_name(uid):
    try:
        profile_url = f'https://osu.ppy.sh/api/get_user?k={Config('osu_api_key', cfg_type=str)}&u={uid}'
        profile = json.loads(await get_url(profile_url, 200))
    except BaseException:
        return False
    userid = profile['user']['user_id']
    username = profile['user']['username']
    if not username:
        username = False

    return userid, username
