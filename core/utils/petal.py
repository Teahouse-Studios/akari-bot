from datetime import datetime, timedelta, UTC

from core.builtins import Bot, I18NContext
from core.builtins.message.elements import I18NContextElement
from core.config import Config
from core.utils.storedata import get_stored_list, update_stored_list


async def gained_petal(msg: Bot.MessageSession, amount: int) -> I18NContextElement:
    """增加花瓣。

    :param msg: 消息会话。
    :param amount: 增加的花瓣数量。
    :returns: 增加花瓣的提示消息。
    """
    if Config("enable_petal", False) and Config("enable_get_petal", False):
        limit = Config("gained_petal_limit", 0)
        amount = limit if amount > limit > 0 else amount
        p = await get_stored_list(msg.target.client_name, "gainedpetal")
        if not p:
            p = [{}]
        p = p[0]
        now = datetime.now(UTC) + msg.timezone_offset
        expired = datetime.combine(
            (now + timedelta(days=1)).date(), datetime.min.time()
        )
        if (
            msg.target.sender_id not in p
            or not p[msg.target.sender_id].get("expired")
            or now.timestamp() > p[msg.target.sender_id]["expired"]
        ):
            p[msg.target.sender_id] = {
                "time": now.timestamp(),
                "expired": expired.timestamp(),
                "amount": amount,
            }
            p = [p]
            await msg.sender_info.modify_petal(amount)
            await update_stored_list(msg.target.client_name, "gainedpetal", p)
            return I18NContext("petal.message.gained.success", amount=amount)
        if limit > 0:
            if p[msg.target.sender_id]["amount"] >= limit:
                return I18NContext("petal.message.gained.limit")
            if p[msg.target.sender_id]["amount"] + amount > limit:
                amount = limit - p[msg.target.sender_id]["amount"]
        p[msg.target.sender_id]["amount"] += amount
        p = [p]
        await msg.sender_info.modify_petal(amount)
        await update_stored_list(msg.target.client_name, "gainedpetal", p)
        return I18NContext("petal.message.gained.success", amount=amount)


async def lost_petal(msg: Bot.MessageSession, amount: int) -> I18NContextElement:
    """减少花瓣。

    :param msg: 消息会话。
    :param amount: 减少的花瓣数量。
    :returns: 减少花瓣的提示消息。
    """
    if Config("enable_petal", False) and Config("enable_get_petal", False):
        limit = Config("lost_petal_limit", 0)
        amount = limit if amount > limit > 0 else amount
        p = await get_stored_list(msg.target.client_name, "lostpetal")
        if not p:
            p = [{}]
        p = p[0]
        now = datetime.now(UTC) + msg.timezone_offset
        expired = datetime.combine(
            (now + timedelta(days=1)).date(), datetime.min.time()
        )
        if (
            msg.target.sender_id not in p
            or not p[msg.target.sender_id].get("expired")
            or now.timestamp() > p[msg.target.sender_id]["expired"]
        ):
            p[msg.target.sender_id] = {
                "time": now.timestamp(),
                "expired": expired.timestamp(),
                "amount": amount,
            }
            p = [p]
            await msg.sender_info.modify_petal(-amount)
            await update_stored_list(msg.target.client_name, "lostpetal", p)
            return I18NContext("petal.message.lost.success", amount=amount)
        if limit > 0:
            if p[msg.target.sender_id]["amount"] >= limit:
                return I18NContext("petal.message.lost.limit")
            if p[msg.target.sender_id]["amount"] + amount > limit:
                amount = limit - p[msg.target.sender_id]["amount"]
        p[msg.target.sender_id]["amount"] += amount
        p = [p]
        await msg.sender_info.modify_petal(-amount)
        await update_stored_list(msg.target.client_name, "lostpetal", p)
        return I18NContext("petal.message.lost.success", amount=amount)


async def cost_petal(msg: Bot.MessageSession, amount: int) -> bool:
    """花费花瓣。

    :param msg: 消息会话。
    :param amount: 花费的花瓣数量。
    :returns: 是否成功处理。
    """
    if Config("enable_petal", False):
        if amount > msg.petal:
            await msg.send_message(I18NContext("petal.message.cost.not_enough"))
            return False
        await msg.sender_info.modify_petal(-amount)
    return True
