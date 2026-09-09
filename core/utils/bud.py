"""花苞（拼手气红包）工具。"""

import asyncio
from datetime import datetime

from tortoise.expressions import F
from tortoise.transactions import in_transaction

from core.builtins.bot import Bot
from core.database.models import SenderUnionInfo, StoredData
from core.utils.random import Random
from core.utils.storedata import get_stored_list, update_stored_list

# 花苞与花瓣一样挂在 union 上、跨平台共享，存储桶复用花瓣的 Union 作用域。
BUD_STORE_SCOPE = "Union"
BUD_STORE_KEY = "petalbuds"
# 花苞有效期（秒）。过期后不可领取，未领取的花瓣退回发送者并清理。
BUD_TTL_SECONDS = 24 * 60 * 60
_bud_mutation_lock = asyncio.Lock()


def split_amount(total: int, count: int) -> list[int]:
    """将 ``total`` 片花瓣随机拆成 ``count`` 份，每份至少 1 片、总和守恒。

    采用带平均值保底的二倍均值法，减少极端小额。

    :param total: 花瓣总数。
    :param count: 拆分份数。
    :raises ValueError: 当 ``count`` 非正或 ``total < count`` 时无法拆分。
    """
    if count <= 0:
        raise ValueError("count must be positive")
    if total < count:
        raise ValueError("total must be >= count")
    shares: list[int] = []
    remaining = total
    minimum = max(1, total // (count * 2))
    for i in range(count, 0, -1):
        if i == 1:
            shares.append(remaining)
            break
        max_amount = 2 * remaining // i
        max_amount = min(max_amount, remaining - minimum * (i - 1))
        amount = Random.randint(minimum, max_amount)
        shares.append(amount)
        remaining -= amount
    return shares


def generate_bud_id(existing_ids: set[str]) -> str:
    """生成一个不与已有花苞冲突的短 ID。"""
    while True:
        bud_id = Random.randstr(8, "ABCDEFGHJKLMNPQRSTUVWXYZ0123456789")
        if bud_id not in existing_ids:
            return bud_id


async def _refund_expired_bud(bud: dict) -> None:
    """将过期花苞中未领取的花瓣退回发送者。"""
    claimed = sum(r.get("amount", 0) for r in bud.get("records", []))
    remaining = bud.get("total", 0) - claimed
    if remaining <= 0:
        return
    sender_union_info = await SenderUnionInfo.filter(union_id=bud.get("sender_union_id")).first()
    if sender_union_info:
        await sender_union_info.modify_petal(remaining)


async def _load_buds() -> list[dict]:
    """读取当前有效的花苞列表，过期花苞退回未领取花瓣并顺带清理。"""
    buds = await get_stored_list(BUD_STORE_SCOPE, BUD_STORE_KEY) or []
    now = datetime.now().timestamp()
    kept: list[dict] = []
    for bud in buds:
        if now - bud.get("created", now) >= BUD_TTL_SECONDS:
            await _refund_expired_bud(bud)
        else:
            kept.append(bud)
    if len(kept) != len(buds):
        await update_stored_list(BUD_STORE_SCOPE, BUD_STORE_KEY, kept)
    return kept


async def create_bud(sender_id: str, sender_union_id: str, total: int, count: int, code: str) -> dict | None:
    """创建花苞并写入存储，口令冲突时返回 ``None``。"""
    async with _bud_mutation_lock:
        async with in_transaction("default") as connection:
            buds, stored = await _load_buds_for_update(connection)
            if any(b.get("code") == code for b in buds):
                return None
            bud = {
                "id": generate_bud_id({b["id"] for b in buds}),
                "sender_id": sender_id,
                "sender_union_id": sender_union_id,
                "total": total,
                "count": count,
                "code": code,
                "shares": split_amount(total, count),
                "records": [],
                "created": datetime.now().timestamp(),
            }
            buds.append(bud)
            await _save_buds(stored, buds, connection)
            return bud


async def find_bud(bud_id: str) -> dict | None:
    """按花苞 ID 查找花苞。"""
    for bud in await _load_buds():
        if bud.get("id") == bud_id:
            return bud
    return None


async def claim_bud(msg: Bot.MessageSession, code: str) -> tuple[str, dict | None, int | None]:
    """领取花苞，返回 ``(状态, 花苞, 领取数量)``。

    状态取值：``not_found`` / ``empty`` / ``already`` / ``success``。
    """
    sender_union_info = msg.session_info.sender_union_info
    union_id = msg.session_info.sender_union_id
    if not sender_union_info or not union_id:
        return "not_found", None, None

    async with _bud_mutation_lock:
        async with in_transaction("default") as connection:
            buds, stored = await _load_buds_for_update(connection)
            bud = next((b for b in buds if b.get("code") == code), None)
            if bud is None:
                return "not_found", None, None
            records = bud["records"]
            if len(records) >= bud["count"]:
                return "empty", bud, None
            if any(r.get("union_id") == union_id for r in records):
                return "already", bud, None

            amount = bud["shares"][len(records)]
            current = await SenderUnionInfo.filter(union_id=union_id).using_db(connection).select_for_update().first()
            if not current:
                return "not_found", None, None
            await SenderUnionInfo.filter(union_id=union_id).using_db(connection).update(petal=F("petal") + amount)
            current.petal += amount
            sender_union_info.petal = current.petal
            records.append({"union_id": union_id, "sender_id": msg.session_info.sender_id, "amount": amount})
            await _save_buds(stored, buds, connection)
            return "success", bud, amount


async def _load_buds_for_update(connection) -> tuple[list[dict], StoredData | None]:
    """在交易中鎖定花苞資料，並把過期退款與清理一併完成。"""
    stored = await (
        StoredData.filter(stored_key=f"{BUD_STORE_SCOPE}|{BUD_STORE_KEY}")
        .using_db(connection)
        .select_for_update()
        .first()
    )
    buds = list(stored.value if stored else [])
    now = datetime.now().timestamp()
    kept = []
    for bud in buds:
        if now - bud.get("created", now) < BUD_TTL_SECONDS:
            kept.append(bud)
            continue
        claimed = sum(r.get("amount", 0) for r in bud.get("records", []))
        remaining = bud.get("total", 0) - claimed
        if remaining > 0:
            sender = await (
                SenderUnionInfo.filter(union_id=bud.get("sender_union_id"))
                .using_db(connection)
                .select_for_update()
                .first()
            )
            if sender:
                await (
                    SenderUnionInfo.filter(union_id=sender.union_id)
                    .using_db(connection)
                    .update(petal=F("petal") + remaining)
                )
    if len(kept) != len(buds):
        buds = kept
    return buds, stored


async def _save_buds(stored: StoredData | None, buds: list[dict], connection) -> None:
    if stored:
        stored.value = buds
        await stored.save(using_db=connection, update_fields=["value"])
    else:
        await StoredData.create(stored_key=f"{BUD_STORE_SCOPE}|{BUD_STORE_KEY}", value=buds, using_db=connection)


__all__ = ["split_amount", "generate_bud_id", "create_bud", "find_bud", "claim_bud"]
