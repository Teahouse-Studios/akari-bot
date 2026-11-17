"""同通道消息认领策略。"""

from __future__ import annotations

import hashlib
import time
from typing import TYPE_CHECKING

from core.builtins.parser.hooks import HookPoint
from core.component import module
from core.database.models import TargetUnionBind
from core.logger import Logger
from core.utils.container import ExpiringTempDict

if TYPE_CHECKING:
    from core.builtins.bot import Bot


CHANNEL_DEDUP_WINDOW = 10

routing = module("parser_routing", hidden=True, load=True, base=True)

channel_claim_cache = routing.state(
    "channel_claim_cache",
    default_factory=ExpiringTempDict,
    preserve=True,
    version=1,
)


@routing.hook(point=HookPoint.CHANNEL_CLAIM, priority=1, name="channels", server_scope=True, timeout=0)
async def _(ctx: "Bot.ParserHookContext"):
    union_id = ctx.msg.session_info.target_union_id
    try:
        channels = await TargetUnionBind.list_channels(union_id) if union_id else {}
    except Exception:
        Logger.exception("Failed to resolve message channels; message execution stopped.")
        return ctx.Stop(scope=ctx.StopScope.MESSAGE, data={"error": "channel_lookup_failed"})
    return ctx.Continue(data={"channels": channels})


@routing.hook(point=HookPoint.CHANNEL_CLAIM, priority=100, name="claim", server_scope=True, timeout=0)
async def _(ctx: "Bot.ParserHookContext"):
    info = ctx.msg.session_info
    union_id = info.target_union_id
    if not union_id:
        return None

    channels = ctx.data.get("channels", {})
    channel_id = info.target_channel_id
    if sum(1 for value in channels.values() if value == channel_id) <= 1:
        return None

    claim_key = str(ctx.data.get("claim_key", ctx.trigger_msg))
    token = f"{union_id}|{channel_id}|{hashlib.sha256(claim_key.encode('utf-8')).hexdigest()}"
    now = time.time()

    # 查询与写入之间不得 await；依靠单线程事件循环维持抢占原子性。
    claimed = channel_claim_cache.get(token)
    claimed_at = claimed.get("timestamp") if claimed else None
    claimed_by = claimed.get("target_id") if claimed else None
    if claimed_at and claimed_by != info.target_id and abs(now - claimed_at) <= CHANNEL_DEDUP_WINDOW:
        Logger.debug(f"Ignored duplicate message claimed by {claimed_by}: {claim_key}")
        return ctx.Stop(scope=ctx.StopScope.CANDIDATE)

    channel_claim_cache[token] = ExpiringTempDict(
        exp=CHANNEL_DEDUP_WINDOW * 3,
        data={"timestamp": now, "target_id": info.target_id},
        root=False,
    )
    return None


__all__ = ["routing"]
