from typing import Union

import ujson as json

from core.types import FetchTarget
from database import BotDBUtil


def get_stored_list(bot: Union[FetchTarget, str], name: str) -> list:
    get = BotDBUtil.Data(bot).get(name=name)
    if not get:
        return []
    else:
        return json.loads(get.value)


def update_stored_list(bot: Union[FetchTarget, str], name: str, value: list):
    edit = BotDBUtil.Data(bot).update(name=name, value=json.dumps(value))
    return edit


__all__ = ['get_stored_list', 'update_stored_list']
