from datetime import datetime, timedelta

from core.builtins.bot import Bot
from core.builtins.message.elements import I18NContextElement
from core.builtins.message.internal import I18NContext
from core.config.base import CoreConfig
from core.utils.random import Random
from core.utils.storedata import get_stored_list, update_stored_list

# 花瓣余额挂在 union 上，日额度也须随之跨平台共享，因此存储不再按客户端分桶，
# 桶内亦按 union 而非平台账号索引；否则一个人绑几个平台就能领几倍的每日上限。
# 花瓣属于用户而非场景，不涉及消息通道维度。
PETAL_STORE_SCOPE = "Union"


async def gained_petal(msg: Bot.MessageSession, amount: int) -> I18NContextElement | None:
    """增加花瓣。

    :param msg: 消息会话。
    :param amount: 增加的花瓣数量。
    :returns: 增加花瓣的提示消息。
    """
    if CoreConfig.enable_petal and CoreConfig.enable_get_petal:
        limit = CoreConfig.petal_gained_limit
        amount = limit if amount > limit > 0 else amount
        # 无用户 union 的会话不持有花瓣，且 union_id 为空会污染存储桶的键
        sender_union_info = msg.session_info.sender_union_info
        union_id = msg.session_info.sender_union_id
        if not sender_union_info or not union_id:
            return None
        p = await get_stored_list(PETAL_STORE_SCOPE, "gainedpetal") or [{}]
        p = p[0]
        now = datetime.now()
        expired = datetime.combine((now + timedelta(days=1)).date(), datetime.min.time())
        if union_id not in p or now.timestamp() > p[union_id]["expired"]:
            p[union_id] = {
                "time": now.timestamp(),
                "expired": expired.timestamp(),
                "amount": amount,
            }
            await sender_union_info.modify_petal(amount)
            await update_stored_list(PETAL_STORE_SCOPE, "gainedpetal", [p])
            return I18NContext("petal.message.gained.success", amount=amount)
        if limit > 0:
            if p[union_id]["amount"] >= limit:
                return I18NContext("petal.message.gained.limit")
            if p[union_id]["amount"] + amount > limit:
                amount = limit - p[union_id]["amount"]
        p[union_id]["amount"] += amount
        await sender_union_info.modify_petal(amount)
        await update_stored_list(PETAL_STORE_SCOPE, "gainedpetal", [p])
        return I18NContext("petal.message.gained.success", amount=amount)


async def lost_petal(msg: Bot.MessageSession, amount: int) -> I18NContextElement | None:
    """减少花瓣。

    :param msg: 消息会话。
    :param amount: 减少的花瓣数量。
    :returns: 减少花瓣的提示消息。
    """
    if CoreConfig.enable_petal and CoreConfig.enable_get_petal:
        limit = CoreConfig.petal_lost_limit
        amount = limit if amount > limit > 0 else amount
        # 同 gained_petal：缺少用户 union 时无从记账
        sender_union_info = msg.session_info.sender_union_info
        union_id = msg.session_info.sender_union_id
        if not sender_union_info or not union_id:
            return None
        p = await get_stored_list(PETAL_STORE_SCOPE, "lostpetal") or [{}]
        p = p[0]
        now = datetime.now()
        expired = datetime.combine((now + timedelta(days=1)).date(), datetime.min.time())
        if union_id not in p or now.timestamp() > p[union_id]["expired"]:
            p[union_id] = {
                "time": now.timestamp(),
                "expired": expired.timestamp(),
                "amount": amount,
            }
            await sender_union_info.modify_petal(-amount)
            await update_stored_list(PETAL_STORE_SCOPE, "lostpetal", [p])
            return I18NContext("petal.message.lost.success", amount=amount)
        if limit > 0:
            if p[union_id]["amount"] >= limit:
                return I18NContext("petal.message.lost.limit")
            if p[union_id]["amount"] + amount > limit:
                amount = limit - p[union_id]["amount"]
        p[union_id]["amount"] += amount
        await sender_union_info.modify_petal(-amount)
        await update_stored_list(PETAL_STORE_SCOPE, "lostpetal", [p])
        return I18NContext("petal.message.lost.success", amount=amount)


async def cost_petal(msg: Bot.MessageSession, amount: int, send_prompt: bool = True) -> bool:
    """花费花瓣。

    :param msg: 消息会话。
    :param amount: 花费的花瓣数量。
    :param send_prompt: 花瓣不足时是否显示提示消息。（默认True）
    :returns: 是否成功处理。
    """
    if CoreConfig.enable_petal:
        sender_union_info = msg.session_info.sender_union_info
        if not sender_union_info:
            return False
        if amount > (msg.session_info.petal or 0):
            if send_prompt:
                await msg.send_message(I18NContext("petal.message.cost.not_enough"))
            return False
        await sender_union_info.modify_petal(-amount)
    return True


async def sign_get_petal(msg: Bot.MessageSession) -> int | None:
    if CoreConfig.enable_petal:

        def _draw_petals() -> int:
            petal = 1
            limit = CoreConfig.petal_sign_limit
            limit = limit if limit > 0 else 5
            rate = CoreConfig.petal_sign_rate
            for _ in range(limit - 1):  # 指数衰减
                if Random.random() < rate:
                    petal += 1
                else:
                    break
            return petal

        amount = _draw_petals()
        sender_union_info = msg.session_info.sender_union_info
        union_id = msg.session_info.sender_union_id
        if not sender_union_info or not union_id:
            return None
        p = await get_stored_list(PETAL_STORE_SCOPE, "signgetpetal") or [{}]
        p = p[0]
        now = datetime.now()
        expired = datetime.combine((now + timedelta(days=1)).date(), datetime.min.time())
        if union_id not in p or now.timestamp() > p[union_id]["expired"]:
            p[union_id] = {
                "time": now.timestamp(),
                "expired": expired.timestamp(),
                "amount": amount,
            }
            await sender_union_info.modify_petal(amount)
            await update_stored_list(PETAL_STORE_SCOPE, "signgetpetal", [p])
            return amount

        return 0


__all__ = ["gained_petal", "lost_petal", "cost_petal"]
