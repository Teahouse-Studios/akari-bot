"""Milky 事件转换。"""

from bots.milky.info import client_name, sender_prefix, target_group_prefix, target_private_prefix
from core.builtins.bot import Bot
from core.builtins.session.info import EventInfo
from core.logger import Logger


async def message_recalled(
    message_id: str | int,
    user_id: str | int,
    group_id: str | int | None = None,
    operator_id: str | int | None = None,
):
    """将撤回通知转换为核心事件。"""
    if group_id is not None:
        target_id = f"{target_group_prefix}|{group_id}"
        target_from = target_group_prefix
    else:
        target_id = f"{target_private_prefix}|{user_id}"
        target_from = target_private_prefix
    try:
        event_info = await EventInfo.assign(
            event_name="message_recalled",
            target_id=target_id,
            target_from=target_from,
            client_name=client_name,
            sender_id=f"{sender_prefix}|{user_id}",
            sender_from=sender_prefix,
            data={
                "message_id": str(message_id),
                "operator_id": f"{sender_prefix}|{operator_id}" if operator_id is not None else None,
            },
            create=False,
        )
    except ValueError:
        # 未记录过的场景不因撤回事件建立身份数据。
        Logger.debug(f"Ignored recall from unknown target {target_id}.")
        return None
    return await Bot.process_event(event_info)
