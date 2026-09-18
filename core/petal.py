import asyncio
from datetime import datetime, timedelta

from tortoise.expressions import F
from tortoise.transactions import in_transaction

from core.builtins.bot import Bot
from core.builtins.message.elements import I18NContextElement
from core.builtins.message.internal import I18NContext
from core.config.base import CoreConfig
from core.database.models import SenderUnionInfo, StoredData
from core.utils.random import Random

# 花瓣余额挂在 union 上，日额度也须随之跨平台共享，因此存储不再按客户端分桶，
# 桶内亦按 union 而非平台账号索引；否则一个人绑几个平台就能领几倍的每日上限。
# 花瓣属于用户而非场景，不涉及消息通道维度。
PETAL_STORE_SCOPE = "Union"
_petal_mutation_lock = asyncio.Lock()


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
        async with _petal_mutation_lock:
            async with in_transaction("default") as connection:
                current = await (
                    SenderUnionInfo.filter(union_id=union_id).using_db(connection).select_for_update().first()
                )
                if not current:
                    return None
                stored = await (
                    StoredData.filter(stored_key=f"{PETAL_STORE_SCOPE}|gainedpetal")
                    .using_db(connection)
                    .select_for_update()
                    .first()
                )
                quota = dict((stored.value if stored else [{}])[0])
                now = datetime.now()
                expired = datetime.combine((now + timedelta(days=1)).date(), datetime.min.time())
                record = quota.get(union_id)
                if not record or now.timestamp() > record["expired"]:
                    record = {"time": now.timestamp(), "expired": expired.timestamp(), "amount": 0}
                    quota[union_id] = record
                changed = min(amount, max(0, limit - record["amount"])) if limit > 0 else amount
                if changed:
                    record["amount"] += changed
                    if stored:
                        stored.value = [quota]
                        await stored.save(using_db=connection, update_fields=["value"])
                    else:
                        await StoredData.create(
                            stored_key=f"{PETAL_STORE_SCOPE}|gainedpetal", value=[quota], using_db=connection
                        )
                    await (
                        SenderUnionInfo.filter(union_id=union_id)
                        .using_db(connection)
                        .update(petal=F("petal") + changed)
                    )
                    current.petal += changed
        if changed:
            sender_union_info.petal = current.petal
            msg.session_info.petal = current.petal
        if changed == 0:
            return I18NContext("petal.message.gained.limit")
        return I18NContext("petal.message.gained.success", amount=changed)


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
        async with _petal_mutation_lock:
            async with in_transaction("default") as connection:
                current = await (
                    SenderUnionInfo.filter(union_id=union_id).using_db(connection).select_for_update().first()
                )
                if not current:
                    return None
                stored = await (
                    StoredData.filter(stored_key=f"{PETAL_STORE_SCOPE}|lostpetal")
                    .using_db(connection)
                    .select_for_update()
                    .first()
                )
                quota = dict((stored.value if stored else [{}])[0])
                now = datetime.now()
                expired = datetime.combine((now + timedelta(days=1)).date(), datetime.min.time())
                record = quota.get(union_id)
                if not record or now.timestamp() > record["expired"]:
                    record = {"time": now.timestamp(), "expired": expired.timestamp(), "amount": 0}
                    quota[union_id] = record
                changed = min(amount, max(0, limit - record["amount"])) if limit > 0 else amount
                if changed:
                    record["amount"] += changed
                    if stored:
                        stored.value = [quota]
                        await stored.save(using_db=connection, update_fields=["value"])
                    else:
                        await StoredData.create(
                            stored_key=f"{PETAL_STORE_SCOPE}|lostpetal", value=[quota], using_db=connection
                        )
                    await (
                        SenderUnionInfo.filter(union_id=union_id)
                        .using_db(connection)
                        .update(petal=F("petal") - changed)
                    )
                    current.petal -= changed
        if changed:
            sender_union_info.petal = current.petal
            msg.session_info.petal = current.petal
        if changed == 0:
            return I18NContext("petal.message.lost.limit")
        return I18NContext("petal.message.lost.success", amount=changed)


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
        amount = int(amount)
        async with in_transaction("default") as connection:
            updated = await (
                sender_union_info.__class__.filter(union_id=sender_union_info.union_id, petal__gte=amount)
                .using_db(connection)
                .update(petal=F("petal") - amount)
            )
        if not updated:
            if send_prompt:
                await msg.send_message(I18NContext("petal.message.cost.not_enough"))
            return False
        sender_union_info.petal = (sender_union_info.petal or 0) - amount
        msg.session_info.petal = sender_union_info.petal
    return True


async def sign_get_petal(msg: Bot.MessageSession) -> int | None:
    if CoreConfig.enable_petal:
        petal_sign_min = CoreConfig.petal_sign_min
        petal_sign_max = CoreConfig.petal_sign_max
        if petal_sign_min > petal_sign_max:
            petal_sign_min, petal_sign_max = petal_sign_max, petal_sign_min

        sign_rate = min(max(float(CoreConfig.petal_sign_rate), 0.0), 1.0)
        amount = petal_sign_min
        while amount < petal_sign_max and Random.random() < sign_rate:
            amount += 1
        sender_union_info = msg.session_info.sender_union_info
        union_id = msg.session_info.sender_union_id
        if not sender_union_info or not union_id:
            return None
        async with _petal_mutation_lock:
            async with in_transaction("default") as connection:
                current = await (
                    SenderUnionInfo.filter(union_id=union_id).using_db(connection).select_for_update().first()
                )
                if not current:
                    return None
                # 签到记录同样挂在 union 上，避免多平台绑定后重复签到。
                stored = await (
                    StoredData.filter(stored_key=f"{PETAL_STORE_SCOPE}|signedpetal")
                    .using_db(connection)
                    .select_for_update()
                    .first()
                )
                quota = dict((stored.value if stored else [{}])[0])
                now = datetime.now()
                expired = datetime.combine((now + timedelta(days=1)).date(), datetime.min.time())
                record = quota.get(union_id)
                if not record or now.timestamp() > record["expired"]:
                    record = {"time": now.timestamp(), "expired": expired.timestamp(), "amount": 0}
                    quota[union_id] = record
                if record["amount"]:
                    # 今日已签到，返回 0 由上层提示“明日再试”。
                    return 0
                record["amount"] = 1
                if stored:
                    stored.value = [quota]
                    await stored.save(using_db=connection, update_fields=["value"])
                else:
                    await StoredData.create(
                        stored_key=f"{PETAL_STORE_SCOPE}|signedpetal", value=[quota], using_db=connection
                    )
                await SenderUnionInfo.filter(union_id=union_id).using_db(connection).update(petal=F("petal") + amount)
                current.petal += amount
        sender_union_info.petal = current.petal
        msg.session_info.petal = current.petal
        return amount


async def settle_petals() -> int:
    """结算所有用户的花瓣余额，并返回成功结算的用户数。"""
    if CoreConfig.enable_petal:
        rebate_rate = min(max(float(CoreConfig.petal_rebate_rate), 0.0), 1.0)
        settled = 0
        for sender_union_info in await SenderUnionInfo.all():
            if await sender_union_info.settle_petal(rebate_rate):
                settled += 1
        return settled
    return 0


__all__ = ["gained_petal", "lost_petal", "cost_petal", "sign_get_petal", "settle_petals"]
