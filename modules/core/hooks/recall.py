"""撤回触发消息后的命令收尾策略。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.builtins.parser.hooks import HookPoint
from core.builtins.session.command_lifecycle import CommandLifecycleRegistry
from core.component import module

if TYPE_CHECKING:
    from core.builtins.bot import Bot


recall = module("command_recall", hidden=True, load=True, base=True)


@recall.hook(point=HookPoint.COMMAND_BEFORE_EXECUTE, priority=200, name="track", server_scope=True)
async def _track_command(ctx: "Bot.ParserHookContext"):
    CommandLifecycleRegistry.attach(ctx.msg)


@recall.hook(point=HookPoint.REGEX_BEFORE_EXECUTE, priority=200, name="track", server_scope=True)
async def _track_regex(ctx: "Bot.ParserHookContext"):
    CommandLifecycleRegistry.attach(ctx.msg)


@recall.hook(point=HookPoint.OUTGOING_BEFORE_SEND, priority=500, name="block", server_scope=True)
async def _block_after_cancel(ctx: "Bot.ParserHookContext"):
    if CommandLifecycleRegistry.output_blocked(ctx.msg):
        return ctx.Stop()


@recall.hook(point=HookPoint.OUTGOING_SENT, priority=500, name="record", server_scope=True)
async def _record_output(ctx: "Bot.ParserHookContext"):
    outgoing = getattr(ctx, "outgoing", None)
    if outgoing is None or outgoing.private:
        # 私信消息不属于命令所在场景，无法按同一条会话记录删除。
        return
    CommandLifecycleRegistry.record_output(ctx.msg, outgoing.message_ids)


@recall.hook(point=HookPoint.FINISHED, priority=500, name="finish", server_scope=True)
async def _finish_command(ctx: "Bot.ParserHookContext"):
    CommandLifecycleRegistry.finish(ctx.msg)
