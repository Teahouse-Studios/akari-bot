from datetime import datetime, timedelta

from core.builtins import Bot, I18NContext
from core.builtins.message.elements import I18NContextElement
from core.config import Config
from core.utils.random import Random
from core.utils.storedata import get_stored_list, update_stored_list


async def gained_petal(msg: Bot.MessageSession, amount: int) -> I18NContextElement:
    """增加花瓣。

    :param msg: 消息会话。
    :param amount: 增加的花瓣数量。
    :returns: 增加花瓣的提示消息。
    """
    if Config("enable_petal", False) and Config("enable_get_petal", False):
        limit = Config("petal_gained_limit", 0)
        amount = limit if amount > limit > 0 else amount
        p = await get_stored_list(msg.target.client_name, "gainedpetal") or [{}]
        p = p[0]
        now = datetime.now()
        expired = datetime.combine(
            (now + timedelta(days=1)).date(), datetime.min.time()
        )
        if msg.target.sender_id not in p \
                or now.timestamp() > p[msg.target.sender_id]["expired"]:
            p[msg.target.sender_id] = {
                "time": now.timestamp(),
                "expired": expired.timestamp(),
                "amount": amount,
            }
            await msg.sender_info.modify_petal(amount)
            await update_stored_list(msg.target.client_name, "gainedpetal", [p])
            return I18NContext("petal.message.gained.success", amount=amount)
        if limit > 0:
            if p[msg.target.sender_id]["amount"] >= limit:
                return I18NContext("petal.message.gained.limit")
            if p[msg.target.sender_id]["amount"] + amount > limit:
                amount = limit - p[msg.target.sender_id]["amount"]
        p[msg.target.sender_id]["amount"] += amount
        await msg.sender_info.modify_petal(amount)
        await update_stored_list(msg.target.client_name, "gainedpetal", [p])
        return I18NContext("petal.message.gained.success", amount=amount)


async def lost_petal(msg: Bot.MessageSession, amount: int) -> I18NContextElement:
    """减少花瓣。

    :param msg: 消息会话。
    :param amount: 减少的花瓣数量。
    :returns: 减少花瓣的提示消息。
    """
    if Config("enable_petal", False) and Config("enable_get_petal", False):
        limit = Config("petal_lost_limit", 0)
        amount = limit if amount > limit > 0 else amount
        p = await get_stored_list(msg.target.client_name, "lostpetal") or [{}]
        p = p[0]
        now = datetime.now()
        expired = datetime.combine(
            (now + timedelta(days=1)).date(), datetime.min.time()
        )
        if msg.target.sender_id not in p \
                or now.timestamp() > p[msg.target.sender_id]["expired"]:
            p[msg.target.sender_id] = {
                "time": now.timestamp(),
                "expired": expired.timestamp(),
                "amount": amount,
            }
            await msg.sender_info.modify_petal(-amount)
            await update_stored_list(msg.target.client_name, "lostpetal", [p])
            return I18NContext("petal.message.lost.success", amount=amount)
        if limit > 0:
            if p[msg.target.sender_id]["amount"] >= limit:
                return I18NContext("petal.message.lost.limit")
            if p[msg.target.sender_id]["amount"] + amount > limit:
                amount = limit - p[msg.target.sender_id]["amount"]
        p[msg.target.sender_id]["amount"] += amount
        await msg.sender_info.modify_petal(-amount)
        await update_stored_list(msg.target.client_name, "lostpetal", [p])
        return I18NContext("petal.message.lost.success", amount=amount)


async def cost_petal(msg: Bot.MessageSession, amount: int, send_prompt: bool = True) -> bool:
    """花费花瓣。

    :param msg: 消息会话。
    :param amount: 花费的花瓣数量。
    :param send_prompt: 花瓣不足时是否显示提示消息。（默认True）
    :returns: 是否成功处理。
    """
    if Config("enable_petal", False):
        if amount > msg.petal:
            if send_prompt:
                await msg.send_message(I18NContext("petal.message.cost.not_enough"))
            return False
        await msg.sender_info.modify_petal(-amount)
    return True


async def sign_get_petal(msg: Bot.MessageSession) -> int:
    if Config("enable_petal", False):
        def _draw_petals() -> int:
            petal = 1
            limit = Config("petal_sign_limit", 5)
            limit = limit if limit > 0 else 5
            rate = Config("petal_sign_rate", 0.5)
            for _ in range(limit - 1):  # 指数衰减
                if Random.random() < rate:
                    petal += 1
                else:
                    break
            return petal

        amount = _draw_petals()
        p = await get_stored_list(msg.target.client_name, "signgetpetal") or [{}]
        p = p[0]
        now = datetime.now()
        expired = datetime.combine(
            (now + timedelta(days=1)).date(), datetime.min.time()
        )
        if msg.target.sender_id not in p \
                or now.timestamp() > p[msg.target.sender_id]["expired"]:
            p[msg.target.sender_id] = {
                "time": now.timestamp(),
                "expired": expired.timestamp(),
                "amount": amount,
            }
            await msg.sender_info.modify_petal(amount)
            await update_stored_list(msg.target.client_name, "signgetpetal", [p])
            return amount

        return 0

__all__ = ["gained_petal", "lost_petal", "cost_petal"]
