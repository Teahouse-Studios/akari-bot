from typing import Union, TYPE_CHECKING

import orjson as json
from tortoise.exceptions import DoesNotExist

from core.database_v2.models import StoredData
if TYPE_CHECKING:
    from core.builtins.message import FetchTarget

from core.exports import exports


async def get_stored_list(bot: Union["FetchTarget", str], name: str) -> list:
    try:
        if isinstance(bot, exports['Bot'].FetchTarget):
            bot = bot.name
        stored_data = await StoredData.filter(stored_key=f"{bot}|{name}").first()
        if not stored_data:
            return []
        return stored_data.value
    except DoesNotExist:
        return []


async def update_stored_list(bot: Union["FetchTarget", str], name: str, value: list):
    if isinstance(bot, exports['Bot'].FetchTarget):
        bot = bot.name
    await StoredData.update_or_create(
        defaults={"value": json.dumps(value)}, stored_key=f"{bot}|{name}"
    )

__all__ = ["get_stored_list", "update_stored_list"]
