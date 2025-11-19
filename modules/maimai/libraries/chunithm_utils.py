from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext
from .chunithm_mapping import *
from ..database.models import DivingProberBindInfo


async def get_diving_prober_bind_info(msg: Bot.MessageSession):
    bind_info = await DivingProberBindInfo.get_by_sender_id(msg, create=False)
    if not bind_info:
        if msg.session_info.sender_from == "QQ":
            payload = {"qq": msg.session_info.get_common_sender_id(), "b50": True}
        else:
            await msg.finish(I18NContext("maimai.message.user_unbound", prefix=msg.session_info.prefixes[0]))
    payload = {"username": bind_info.username, "b50": True}
    return payload


def get_diff(diff):
    diff = diff.lower()
    diff_list_lower = [label.lower() for label in diff_list]

    if diff in diff_list_zhs:
        level = diff_list_zhs.index(diff)
    elif diff in diff_list_zht:
        level = diff_list_zht.index(diff)
    elif diff in diff_list_abbr:
        level = diff_list_abbr.index(diff)
    elif diff in diff_list_lower:
        level = diff_list_lower.index(diff)
    else:
        level = 0
    return level
