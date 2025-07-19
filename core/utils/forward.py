from core.builtins.bot import Bot
from core.utils.storedata import get_stored_list


async def check_enable_forward_msg():
    get_ = await get_stored_list(Bot.Info.client_name, "forward_msg")
    if get_ and isinstance(get_[0], dict):
        if 'status' in get_[0]:
            return get_[0]['status']
    return True
