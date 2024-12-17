import traceback

import orjson as json

from core.builtins import Bot
from core.config import Config
from core.constants.exceptions import ConfigValueError
from core.logger import Logger
from core.utils.http import get_url


async def get_profile_name(msg: Bot.MessageSession, uid):
    if not Config("osu_api_key", cfg_type=str, secret=True):
        raise ConfigValueError(msg.locale.t("error.config.secret.not_found"))
    try:
        profile_url = f"https://osu.ppy.sh/api/get_user?k={Config('osu_api_key', secret=True, cfg_type=str)}&u={uid}"
        profile = json.loads(await get_url(profile_url, 200))[0]
        userid = profile["user_id"]
        username = profile["username"]
    except ValueError as e:
        if str(e).startswith("401"):
            raise ConfigValueError(msg.locale.t("error.config.invalid"))
        Logger.error(traceback.format_exc())
        return False
    except BaseException:
        return False

    return userid, username
