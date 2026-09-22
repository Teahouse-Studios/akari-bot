"""消息入口的内置策略。"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import I18NContext
from core.builtins.message.internal import ActionText
from core.builtins.parser.hooks import HookPoint
from core.builtins.session.lock import ExecutionLockList
from core.component import module
from core.config.base import CoreConfig
from core.database.models import SenderUnionInfo
from core.loader import ModulesManager
from core.logger import Logger
from core.utils.container import ExpiringTempDict

if TYPE_CHECKING:
    from core.builtins.bot import Bot


policies = module("parser_policies", hidden=True, load=True, base=True)

# 场景冷却属于策略状态；由模块 runtime 管理，热重载同版本时保留。
target_cooldown_counter = policies.state(
    "target_cooldown_counter",
    default_factory=ExpiringTempDict,
    preserve=True,
    version=1,
)


def _sender_scope_key(msg) -> str | None:
    return msg.session_info.sender_union_id or msg.session_info.sender_id


@policies.hook(point=HookPoint.SESSION_READY, priority=10, name="inbound_gate", server_scope=True)
async def _inbound_gate(ctx: "Bot.ParserHookContext"):
    msg = ctx.msg
    info = msg.session_info
    sender_info = info.sender_union_info

    if info.sender_id in CoreConfig.ignored_sender:
        return ctx.Stop(scope=ctx.StopScope.MESSAGE)

    target_union_info = info.target_union_info
    if target_union_info and info.sender_id in target_union_info.list_peer_bots(info.target_id):
        Logger.debug(f"Ignored message from another client: {info.sender_id}")
        return ctx.Stop(scope=ctx.StopScope.MESSAGE)

    if sender_info and sender_info.blocked and not (sender_info.trusted or sender_info.superuser):
        return ctx.Stop(scope=ctx.StopScope.MESSAGE)
    if info.sender_union_id in (info.banned_users or []) and not msg.check_super_user():
        return ctx.Stop(scope=ctx.StopScope.MESSAGE)
    return None


async def _check_target_cooldown(msg, ctx: "Bot.ParserHookContext"):
    cooldown_time = int(msg.session_info.target_union_info.target_data.get("cooldown_time", 0))
    if not cooldown_time or await msg.check_permission():
        return None

    target_record = target_cooldown_counter[msg.session_info.channel_key]
    sender_key = _sender_scope_key(msg)
    sender_record = target_record.get(sender_key)
    if not sender_record:
        sender_record = ExpiringTempDict(data={"notified": False}, exp=cooldown_time, root=False)
        target_record[sender_key] = sender_record
        return None

    if not sender_record.is_expired():
        if not sender_record.get("notified", False):
            sender_record["notified"] = True
            elapsed = cooldown_time - (time.time() - sender_record.ts)
            return ctx.Stop(message=I18NContext("message.cooldown.manual", time=int(elapsed)))
        return ctx.Stop()

    sender_record.refresh()
    sender_record["notified"] = False
    sender_record.exp = cooldown_time
    return None


@policies.hook(point=HookPoint.COMMAND_PREPARE, priority=5, name="cooldown", server_scope=True, timeout=0)
async def _command_cooldown(ctx: "Bot.ParserHookContext"):
    return await _check_target_cooldown(ctx.msg, ctx)


@policies.hook(point=HookPoint.REGEX_PREPARE, priority=15, name="cooldown", server_scope=True, timeout=0)
async def _regex_cooldown(ctx: "Bot.ParserHookContext"):
    if not ctx.data.get("show_typing", True):
        return None
    return await _check_target_cooldown(ctx.msg, ctx)


@policies.hook(point=HookPoint.COMMAND_ROUTE, priority=20, name="muted", server_scope=True)
async def _command_muted(ctx: "Bot.ParserHookContext"):
    if ctx.msg.session_info.muted and ctx.command_first_word != "mute":
        return ctx.Stop()
    return None


@policies.hook(point=HookPoint.OUTGOING_BEFORE_SEND, priority=10, name="muted_outgoing", server_scope=True)
async def _outgoing_muted(ctx: "Bot.ParserHookContext"):
    info = ctx.session_info
    if info.fetch and info.muted:
        Logger.debug(f"Suppressed proactive message to muted target: {info.target_id}")
        return ctx.Stop()
    return None


async def _check_superuser_or_authorized(msg, module_name: str) -> bool:
    if msg.check_super_user():
        return True
    related_module_names = ModulesManager.get_module_and_alias_first_words(module_name) or [module_name]
    sender_info = msg.session_info.sender_union_info
    auth_list = sender_info.sender_data.get("module_auth", []) if sender_info else []
    for entry in auth_list:
        if entry.get("module") in related_module_names:
            authorizer = await SenderUnionInfo.get_by_sender_id(entry["authorized_by"], create=False)
            if authorizer and authorizer.superuser:
                return True
    return False


@policies.hook(point=HookPoint.COMMAND_PREPARE, priority=30, name="module_route", server_scope=True, timeout=0)
async def _module_route(ctx: "Bot.ParserHookContext"):
    module = ctx.data.get("module")
    if module is None:
        return None
    msg = ctx.msg
    module_name = ctx.command_first_word or ctx.module_name or module.module_name

    if not module.command_list.set:
        if module.unsupported_reason(msg.session_info) or not module.desc:
            if not module.desc:
                return ctx.Stop(message=I18NContext("error.module.unbound", module=module_name))
            return ctx.Stop()
        desc = [I18NContext("parser.module.desc", desc=msg.session_info.locale.t_str(module.desc))]
        if module_name not in (msg.session_info.enabled_modules or []):
            desc.append(
                I18NContext(
                    "parser.module.disabled.prompt",
                    module=module_name,
                    cmd=ActionText(f"{msg.session_info.prefixes[0]}enable {module_name}"),
                )
            )
        return ctx.Stop(message=MessageChain.assign(desc))

    from core.builtins.bot import Bot

    bot = Bot
    if module.required_base_superuser and msg.session_info.sender_id not in bot.base_superuser_list:
        return ctx.Stop(message=I18NContext("parser.superuser.permission.denied"))
    if module.required_superuser and not await _check_superuser_or_authorized(msg, module_name):
        return ctx.Stop(message=I18NContext("parser.superuser.permission.denied"))
    if module.required_admin and not await msg.check_permission():
        return ctx.Stop(message=I18NContext("parser.admin.permission.denied.module", module=module_name))

    if (
        not module.base
        and module_name not in (msg.session_info.enabled_modules or [])
        and msg.session_info.require_enable_modules
    ):
        if not await msg.check_permission():
            return ctx.Stop(message=I18NContext("parser.module.disabled", module=module_name))
        await msg.send_message(
            I18NContext(
                "parser.module.disabled.prompt",
                module=module_name,
                cmd=ActionText(f"{msg.session_info.prefixes[0]}enable {module_name}"),
            )
        )
        if not await msg.wait_confirm(I18NContext("parser.module.disabled.to_enable"), no_confirm_action=False):
            return ctx.Stop()
        await msg.session_info.target_union_info.config_module(module_name)
        await msg.send_message(I18NContext("core.message.module.enable.success", module=module_name))
    return None


@policies.hook(point=HookPoint.COMMAND_BEFORE_EXECUTE, priority=10, name="command_authorize", server_scope=True)
async def _command_authorize(ctx: "Bot.ParserHookContext"):
    command = ctx.data.get("command")
    if command is None:
        return None
    msg = ctx.msg
    module_name = ctx.module_name or ctx.command_first_word or ""
    from core.builtins.bot import Bot

    bot = Bot
    if command.required_base_superuser and msg.session_info.sender_id not in bot.base_superuser_list:
        return ctx.Stop(message=I18NContext("parser.superuser.permission.denied"))
    if command.required_superuser and not await _check_superuser_or_authorized(msg, module_name):
        return ctx.Stop(message=I18NContext("parser.superuser.permission.denied"))
    if command.required_admin and not await msg.check_permission():
        return ctx.Stop(message=I18NContext("parser.admin.permission.denied.command"))
    if (
        not command.load
        or msg.session_info.target_from in command.exclude_from
        or msg.session_info.client_name in command.exclude_from
        or (
            "*" not in command.available_for
            and msg.session_info.target_from not in command.available_for
            and msg.session_info.client_name not in command.available_for
        )
    ):
        return ctx.Stop()
    return None


@policies.hook(point=HookPoint.COMMAND_BEFORE_EXECUTE, priority=100, name="locked_prompt", server_scope=True)
async def _locked_prompt(ctx: "Bot.ParserHookContext"):
    if ctx.data.get("locked"):
        await ctx.msg.send_message(I18NContext("parser.command.running.prompt"))
        return ctx.Stop()
    return None


def should_skip_regex(trigger_msg: str) -> bool:
    prefixes = tuple(prefix for prefix in CoreConfig.regex_disable_prefix if isinstance(prefix, str) and prefix)
    return bool(prefixes) and trigger_msg.startswith(prefixes)


@policies.hook(point=HookPoint.REGEX_ROUTE, priority=10, name="route", server_scope=True)
async def _regex_route(ctx: "Bot.ParserHookContext"):
    msg = ctx.msg
    trigger_msg = msg.trigger_msg
    if should_skip_regex(trigger_msg) or msg.session_info.muted:
        return ctx.Stop()
    if msg.session_info.use_running_mention and msg.session_info.bot_name:
        if msg.session_info.bot_name.lower() in trigger_msg.lower() and await ExecutionLockList.is_locked(msg):
            return ctx.Stop(message=I18NContext("parser.command.running.prompt2"))
    return None


@policies.hook(point=HookPoint.REGEX_PREPARE, priority=5, name="permission", server_scope=True)
async def _regex_permission(ctx: "Bot.ParserHookContext"):
    rfunc = ctx.data.get("regex")
    module_name = ctx.module_name or ""
    if rfunc is None:
        return None
    from core.builtins.bot import Bot

    bot = Bot
    if rfunc.required_base_superuser and ctx.msg.session_info.sender_id not in bot.base_superuser_list:
        return ctx.Stop()
    if rfunc.required_superuser and not await _check_superuser_or_authorized(ctx.msg, module_name):
        return ctx.Stop()
    if rfunc.required_admin and not await ctx.msg.check_permission():
        return ctx.Stop()
    return None


@policies.hook(point=HookPoint.COMMAND_UNMATCHED, priority=100, name="default_feedback", server_scope=True)
async def _default_command_feedback(ctx: "Bot.ParserHookContext"):
    from .errors import INVALID_COMMAND_EMOTES, send_common_emote

    kind = ctx.data.get("unmatched_kind")
    if kind in {"syntax", "template"}:
        if not ctx.data.get("suppress_invalid_prompt", False):
            await ctx.msg.send_message(
                I18NContext(
                    "parser.command.invalid.syntax",
                    module=ctx.command_first_word or "",
                    cmd=ActionText(f"{ctx.msg.session_info.prefixes[0]}help {ctx.command_first_word or ''}"),
                )
            )
            await send_common_emote(ctx.msg, INVALID_COMMAND_EMOTES)
        return ctx.Handled()
    if kind == "unloaded":
        await ctx.msg.send_message(I18NContext("parser.module.unloaded", module=ctx.command_first_word or ""))
        return ctx.Handled()
    if ctx.msg.session_info.invalid_module_prompt_enabled:
        await ctx.msg.send_message(
            I18NContext("parser.command.invalid.module", cmd=ActionText(f"{ctx.msg.session_info.prefixes[0]}help"))
        )
        await send_common_emote(ctx.msg, INVALID_COMMAND_EMOTES)
    return ctx.Handled()


__all__ = ["policies"]
