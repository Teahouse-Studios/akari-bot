import traceback

import orjson as json

from core.builtins import Bot
from core.constants.exceptions import ConfigValueError
from core.logger import Logger
from core.utils.http import get_url


async def get_profile_name(msg: Bot.MessageSession, uid, api_key):
    if not api_key:
        raise ConfigValueError("[I18N:error.config.secret.not_found]")
    try:
        profile_url = f"https://osu.ppy.sh/api/get_user?k={api_key}&u={uid}"
        profile = json.loads(await get_url(profile_url, 200))[0]
        userid = profile["user_id"]
        username = profile["username"]
    except ValueError as e:
        if str(e).startswith("401"):
            raise ConfigValueError("[I18N:error.config.invalid]")
        Logger.error(traceback.format_exc())
        return False
    except Exception:
        return False

    return userid, username
