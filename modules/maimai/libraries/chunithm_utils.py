from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext
from core.constants.exceptions import ConfigValueError
from core.utils.http import get_url
from .chunithm_mapping import *
from ..database.models import DivingProberBindInfo, LxnsProberBindInfo


async def get_diving_prober_bind_info(msg: Bot.MessageSession, **kwargs):
    bind_info = await DivingProberBindInfo.get_by_sender_id(msg, create=False)
    if not bind_info:
        if msg.session_info.sender_from == "QQ":
            return {"qq": msg.session_info.get_common_sender_id()} | kwargs
        else:
            await msg.finish(I18NContext("chunithm.message.user_unbound.df", prefix=msg.session_info.prefixes[0]))
    else:
        return {"username": bind_info.username} | kwargs


async def get_lxns_prober_bind_info(msg: Bot.MessageSession):
    bind_info = await LxnsProberBindInfo.get_by_sender_id(msg, create=False)
    if not bind_info:
        if msg.session_info.sender_from == "QQ":
            try:
                profile_url = f"https://maimai.lxns.net/api/v0/chunithm/player/qq/{
                    msg.session_info.get_common_sender_id()}"
                profile_data = await get_url(
                    profile_url,
                    status_code=200,
                    headers={"User-Agent": "AkariBot/1.0", "Authorization": LX_DEVELOPER_TOKEN, "Content-Type": "application/json", "accept": "*/*"},
                    fmt="json"
                )
                return str(profile_data["data"]["friend_code"])
            except Exception as e:
                if str(e).startswith(("400", "404")):
                    await msg.finish(I18NContext("maimai.message.user_not_found.lx"))
                elif str(e).startswith("401"):
                    raise ConfigValueError("{I18N:error.config.invalid}")
                elif str(e).startswith("403"):
                    await msg.finish(I18NContext("maimai.message.forbidden"))
                else:
                    raise e
        else:
            await msg.finish(I18NContext("chunithm.message.user_unbound.lx", prefix=msg.session_info.prefixes[0]))
    return bind_info.friend_code


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
