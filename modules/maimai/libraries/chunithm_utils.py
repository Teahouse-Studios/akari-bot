from core.builtins.bot import Bot
from core.builtins.message.internal import ActionText, I18NContext
from .chunithm_mapping import *
from .divingfish_oauth import diving_fish_bind_usable
from ..database.models import DivingProberBindInfo, LxnsProberBindInfo


async def get_diving_prober_bind_info(msg: Bot.MessageSession):
    """取得该用户的水鱼绑定记录。

    CHUNITHM 成绩由 OAuth 端点提供，查询对象由令牌决定，因此必须存在这位用户自己的授权记录。

    :param msg: 消息会话。
    :return: 该用户的绑定记录。
    """
    bind_info = await DivingProberBindInfo.get_by_sender_id(msg, create=False)
    if not diving_fish_bind_usable(bind_info):
        await msg.finish(
            I18NContext(
                "chunithm.message.user_unbound.df",
                cmd=ActionText(f"{msg.session_info.prefixes[0]}chunithm bind df"),
            )
        )
    return bind_info


async def get_lxns_prober_bind_info(msg: Bot.MessageSession):
    """取得该用户的落雪绑定记录。

    查询对象由令牌决定，故必须存在这位用户自己的授权记录。

    :param msg: 消息会话。
    :return: 该用户的绑定记录。
    """
    bind_info = await LxnsProberBindInfo.get_by_sender_id(msg, create=False)
    if not bind_info or not bind_info.refresh_token:
        await msg.finish(
            I18NContext(
                "chunithm.message.user_unbound.lx",
                cmd=ActionText(f"{msg.session_info.prefixes[0]}chunithm bind lx"),
            )
        )
    return bind_info


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
