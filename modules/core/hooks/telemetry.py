"""通过 parser 观察入口写入 AnalyticsData 与 Info 计数。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.builtins.parser.hooks import HookPoint
from core.component import module
from core.config.base import CoreConfig
from core.constants.info import Info
from core.database.models import AnalyticsData
from core.logger import Logger

if TYPE_CHECKING:
    from core.builtins.bot import Bot


def _enable_analytics() -> bool:
    return bool(getattr(CoreConfig, "enable_analytics", False))


telemetry = module("telemetry", hidden=True, load=True, base=True)


@telemetry.hook(point=HookPoint.EXECUTION_FINISHED, priority=50, name="record", server_scope=True)
async def _(ctx: "Bot.ParserHookContext"):
    Info.command_parsed += 1
    if not _enable_analytics():
        return None
    data = ctx.data
    try:
        await AnalyticsData.create(
            target_id=ctx.msg.session_info.target_id,
            sender_id=ctx.msg.session_info.sender_id,
            target_union_id=ctx.msg.session_info.target_union_id,
            sender_union_id=ctx.msg.session_info.sender_union_id,
            command=ctx.msg.trigger_msg,
            module_name=data.get("module_name") or ctx.module_name or "",
            module_type=data.get("module_type", "normal"),
        )
    except Exception:
        # 采集失败不得影响命令收尾与正则遍历
        Logger.exception("Telemetry hook failed to write AnalyticsData.")


@telemetry.hook(point=HookPoint.FINISHED, priority=50, name="message_parsed", server_scope=True)
async def _(ctx: "Bot.ParserHookContext"):
    Info.message_parsed += 1


__all__ = ["telemetry"]
