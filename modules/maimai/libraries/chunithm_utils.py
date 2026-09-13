from core.builtins.bot import Bot
from core.builtins.message.internal import ActionText, I18NContext
from core.constants.exceptions import ConfigValueError
from core.utils.http import get_url
from .chunithm_mapping import *
from ..database.models import DivingProberBindInfo, LxnsProberBindInfo


async def get_diving_prober_bind_info(msg: Bot.MessageSession):
    """取得该用户的水鱼绑定记录。

    CHUNITHM 成绩由 OAuth 端点提供，查询对象由令牌决定，因此必须存在这位用户自己的授权记录。

    :param msg: 消息会话。
    :return: 该用户的绑定记录。
    """
    bind_info = await DivingProberBindInfo.get_by_sender_id(msg, create=False)
    if not bind_info or not bind_info.refresh_token:
        await msg.finish(
            I18NContext(
                "chunithm.message.user_unbound.df",
                cmd=ActionText(f"{msg.session_info.prefixes[0]}chunithm bind df"),
            )
        )
    return bind_info


async def get_lxns_prober_bind_info(msg: Bot.MessageSession):
    """取得该用户的落雪身份。

    已授权 OAuth 的绑定直接返回绑定记录，查询对象由令牌决定；仅有好友码的旧绑定沿用开发者
    令牌接口，查询对象是好友码。QQ 平台上的无绑定用户仍可按 QQ 号反查好友码。

    :param msg: 消息会话。
    :return: 该用户的绑定记录，或仅有好友码的旧绑定的好友码。
    """
    bind_info = await LxnsProberBindInfo.get_by_sender_id(msg, create=False)
    if bind_info and bind_info.refresh_token:
        return bind_info
    if bind_info and bind_info.friend_code:
        return bind_info.friend_code
    if msg.session_info.sender_from == "QQ":
        try:
            profile_url = f"https://maimai.lxns.net/api/v0/chunithm/player/qq/{msg.session_info.get_common_sender_id()}"
            profile_data = await get_url(
                profile_url,
                status_code=200,
                headers={
                    "User-Agent": "AkariBot/1.0",
                    "Authorization": LX_DEVELOPER_TOKEN,
                    "Content-Type": "application/json",
                    "accept": "*/*",
                },
                fmt="json",
            )
            return str(profile_data.get("data", {}).get("friend_code", ""))
        except Exception as e:
            if str(e).startswith(("400", "404")):
                await msg.finish(I18NContext("maimai.message.user_not_found.lx"))
            elif str(e).startswith("401"):
                raise ConfigValueError("{I18N:error.config.invalid}")
            elif str(e).startswith("403"):
                await msg.finish(I18NContext("maimai.message.forbidden"))
            else:
                raise e
    await msg.finish(
        I18NContext(
            "chunithm.message.user_unbound.lx",
            cmd=ActionText(f"{msg.session_info.prefixes[0]}chunithm bind lx"),
        )
    )


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
