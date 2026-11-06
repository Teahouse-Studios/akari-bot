import asyncio
from datetime import datetime, timedelta

from apscheduler.triggers.cron import CronTrigger
from tortoise.expressions import F
from tortoise.transactions import in_transaction

from core.builtins.bot import Bot
from core.builtins.message.elements import I18NContextElement
from core.builtins.message.internal import I18NContext
from core.config.base import CoreConfig
from core.database.models import SenderUnionInfo, StoredData
from core.logger import Logger
from core.utils.random import Random
from core.utils.timezone import core_now, core_tz

# 花瓣余额挂在 union 上，日额度也须随之跨平台共享，因此存储不再按客户端分桶，
# 桶内亦按 union 而非平台账号索引；否则一个人绑几个平台就能领几倍的每日上限。
# 每日周期按触发场景的时区计算，记录内保存周期偏移，跨场景共用同一条记录。
PETAL_STORE_SCOPE = "Union"
PETAL_CYCLE_STORE_KEY = f"{PETAL_STORE_SCOPE}|petalcycle"
_petal_mutation_lock = asyncio.Lock()


def _next_local_midnight(now: datetime) -> datetime:
    return datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), tzinfo=now.tzinfo)


def _cycle_record(quota: dict, union_id: str, now: datetime, offset_label: str) -> dict:
    record = quota.get(union_id)
    if isinstance(record, dict) and now.timestamp() < record.get("expired", 0):
        return record
    previous_offset = record.get("offset") if isinstance(record, dict) else offset_label
    # 场景时区变更后的首个周期按 24 小时滚动，避免改时区提前刷新。
    expired = now + timedelta(days=1) if previous_offset != offset_label else _next_local_midnight(now)
    record = {
        "time": now.timestamp(),
        "expired": expired.timestamp(),
        "amount": 0,
        "offset": offset_label,
    }
    quota[union_id] = record
    return record


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
                record = _cycle_record(quota, union_id, msg.session_info.now(), msg.session_info.tz_label)
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
                record = _cycle_record(quota, union_id, msg.session_info.now(), msg.session_info.tz_label)
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
                record = _cycle_record(quota, union_id, msg.session_info.now(), msg.session_info.tz_label)
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


async def _reset_rows(connection, keep_rate: float) -> int:
    rows = await SenderUnionInfo.filter(petal__gt=0).using_db(connection).select_for_update()
    if not rows:
        return 0
    for row in rows:
        row.petal = max(0, int(row.petal * keep_rate))
    # 分批写入，避免用户量大时单条 UPDATE 超出数据库的语句长度上限。
    await SenderUnionInfo.bulk_update(rows, fields=["petal"], batch_size=500, using_db=connection)
    return len(rows)


def _decode_reset_due(stored: StoredData | None) -> datetime | None:
    if not stored or not stored.value:
        return None
    try:
        due = datetime.fromisoformat(str(stored.value[0]))
    except (TypeError, ValueError):
        Logger.warning("Invalid petal settlement marker, treated as missing.")
        return None
    return due if due.tzinfo else due.replace(tzinfo=core_tz())


async def reset_petals_if_due() -> int:
    if not CoreConfig.enable_petal:
        return 0
    try:
        trigger = CronTrigger.from_crontab(CoreConfig.petal_reset_crontab, timezone=core_tz())
    except (AttributeError, TypeError, ValueError):
        Logger.exception(f"Invalid petal_reset_crontab {CoreConfig.petal_reset_crontab!r}, skipped reset.")
        return 0
    now = core_now(trigger.timezone)
    # 取严格晚于当前时刻的下一次触发时间：当前恰好落在触发点上时也不会重复结算。
    following = trigger.get_next_fire_time(now, now)
    if following is None:
        Logger.warning("Petal reset crontab has no future fire time, skipped reset.")
        return 0
    keep_rate = min(max(float(CoreConfig.petal_keep_rate), 0.0), 1.0)
    try:
        async with _petal_mutation_lock:
            async with in_transaction("default") as connection:
                stored = await (
                    StoredData.filter(stored_key=PETAL_CYCLE_STORE_KEY).using_db(connection).select_for_update().first()
                )
                due = _decode_reset_due(stored)
                if due is not None and now < due:
                    return 0
                reset_users = await _reset_rows(connection, keep_rate)
                if stored is None:
                    await StoredData.create(
                        stored_key=PETAL_CYCLE_STORE_KEY,
                        value=[following.isoformat()],
                        using_db=connection,
                    )
                else:
                    stored.value = [following.isoformat()]
                    await stored.save(using_db=connection, update_fields=["value"])
    except Exception:
        # 周期结算属于后台维护，失败只记录并在下个检查点重试，不中断同批次的其它维护工作。
        Logger.exception("Failed to reset petals, will retry on the next check.")
        return 0
    Logger.info(f"Petal reset finished: {reset_users} user(s) reseted, next reset period at {following.isoformat()}.")
    return reset_users


__all__ = ["gained_petal", "lost_petal", "cost_petal", "sign_get_petal", "reset_petals_if_due"]
