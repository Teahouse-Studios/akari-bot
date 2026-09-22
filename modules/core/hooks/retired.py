"""退役客户端的消息路由策略。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.builtins.parser.hooks import HookPoint
from core.component import module
from core.database.models import TargetUnionBind
from core.utils.retired import (
    is_module_allowed_when_retired,
    is_retired_client,
    is_retired_target,
    should_yield_channel,
)

if TYPE_CHECKING:
    from core.builtins.bot import Bot


retired = module("retired_policy", hidden=True, load=True, base=True)


@retired.hook(point=HookPoint.COMMAND_ROUTE, priority=1, name="route_gate", server_scope=True)
async def _(ctx: "Bot.ParserHookContext"):
    if not is_retired_client(ctx.msg.session_info.client_name):
        return None
    # 模块别名可以把白名单命令并入其它模块（merge 现解析为 bind），此时模块名不再落入
    # 白名单，回退到用户别名改写前实际输入的首词继续判定；其它首词依旧一律拦截。
    original_word = getattr(ctx.msg, "command_original_word", "")
    if is_module_allowed_when_retired(ctx.module_name or ctx.command_first_word) or is_module_allowed_when_retired(
        original_word
    ):
        return None
    return ctx.Stop(scope=ctx.StopScope.MESSAGE)


@retired.hook(point=HookPoint.SESSION_BEFORE_WAIT, priority=10, name="wait_task", server_scope=True, timeout=0)
async def _(ctx: "Bot.ParserHookContext"):
    info = ctx.msg.session_info
    if not is_retired_target(info.target_id) or not info.target_union_id:
        return None
    channels = await TargetUnionBind.list_channels(info.target_union_id)
    if should_yield_channel(info.target_id, channels, info.target_channel_id):
        return ctx.Continue(data={"skip_wait_tasks": True})
    return None


@retired.hook(point=HookPoint.REGEX_CANDIDATE, priority=10, name="regex_gate", server_scope=True)
async def _(ctx: "Bot.ParserHookContext"):
    if is_retired_client(ctx.msg.session_info.client_name) and not is_module_allowed_when_retired(ctx.module_name):
        return ctx.Stop(scope=ctx.StopScope.CANDIDATE)
    return None


@retired.hook(point=HookPoint.CHANNEL_CLAIM, priority=10, name="yield", server_scope=True, timeout=0)
async def _(ctx: "Bot.ParserHookContext"):
    info = ctx.msg.session_info
    if not info.target_union_id:
        return None
    channels = ctx.data["channels"]
    channel_id = info.target_channel_id
    channel_targets = [target_id for target_id, cid in channels.items() if cid == channel_id]
    if len(channel_targets) <= 1:
        return None

    routed_available = ctx.data.get("routed_command_available")
    mixed_channel = any(is_retired_target(target_id) for target_id in channel_targets) and any(
        not is_retired_target(target_id) for target_id in channel_targets
    )
    if mixed_channel and routed_available is False:
        return ctx.Stop(scope=ctx.StopScope.CANDIDATE)
    if routed_available is not True and should_yield_channel(info.target_id, channels, channel_id):
        return ctx.Stop(scope=ctx.StopScope.CANDIDATE)
    return None


__all__ = ["retired"]
