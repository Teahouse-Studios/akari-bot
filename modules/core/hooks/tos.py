"""ToS 限流、临时封禁与滥用上报。"""

from __future__ import annotations

import re
import time
from functools import wraps
from typing import TYPE_CHECKING

from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import I18NContext
from core.builtins.parser.hooks import Handled, HookPoint, Stop, StopScope
from core.component import module
from core.config.base import CoreConfig
from core.constants.exceptions import AbuseWarning, SendMessageFailed, SessionFinished, WaitCancelException
from core.loader import ModulesManager
from core.logger import Logger
from core.smtp import send_report
from core.utils.container import ExpiringTempDict, TokenBucket

if TYPE_CHECKING:
    from core.builtins.bot import Bot

_I18N_KEY_RE = re.compile(r"^\{I18N:([^}]+)}$")


def _enable_tos() -> bool:
    return bool(getattr(CoreConfig, "enable_tos", False))


def _warning_counts() -> int:
    return int(getattr(CoreConfig, "tos_warning_counts", 0) or 0)


def _temp_ban_time() -> int:
    configured = int(getattr(CoreConfig, "tos_temp_ban_time", 0) or 0)
    return configured if configured > 0 else 300


def _report_targets():
    return getattr(CoreConfig, "report_targets", []) or []


def _resolve_reason_text(msg, reason: str) -> str:
    text = str(reason)
    matched = _I18N_KEY_RE.fullmatch(text)
    if matched:
        return msg.session_info.locale.t(matched.group(1))
    return msg.session_info.locale.t_str(text)


tos = module("tos", hidden=True, load=True, base=True)


def _enforce_tos(function):

    @wraps(function)
    async def enforced(ctx: "Bot.ParserHookContext"):
        try:
            return await function(ctx)
        except (Exception, SendMessageFailed, SessionFinished, WaitCancelException):
            Logger.exception("ToS enforcement failed; message execution stopped.")
            return Stop(scope=StopScope.MESSAGE, data={"error": "tos_check_failed"})

    return enforced


# 同版本 reload 保留限流与临封状态；版本变化时重建
_buckets_same = tos.state(
    "buckets_same",
    default_factory=ExpiringTempDict,
    preserve=True,
    version=1,
)
_buckets_all = tos.state(
    "buckets_all",
    default_factory=ExpiringTempDict,
    preserve=True,
    version=1,
)
# 临封计数：同版本热重载时保留，版本变化时重建。
temp_ban_counter = tos.state(
    "temp_ban_counter",
    default_factory=lambda: ExpiringTempDict(exp=_temp_ban_time()),
    preserve=True,
    version=1,
)


def sender_scope_key(msg) -> str | None:
    return msg.session_info.sender_union_id or msg.session_info.sender_id


async def check_temp_ban(target) -> int | bool:
    ban_info = temp_ban_counter.get(target)
    if ban_info:
        ban_time_remain = int(_temp_ban_time() - (time.time() - ban_info.ts))
        return ban_time_remain
    return False


async def remove_temp_ban(target):
    if await check_temp_ban(target):
        del temp_ban_counter[target]


async def tos_report(sender: str, target: str, reason: str, banned: bool = False):
    """上报滥用行为。"""
    warn_template = MessageChain.assign(
        [I18NContext("tos.message.report", sender=sender, target=target, disable_joke=True)]
    )
    warn_template.append(I18NContext("tos.message.reason", reason=reason, disable_joke=True))
    if banned:
        action = str(I18NContext("tos.message.action.blocked", disable_joke=True))
    else:
        action = str(I18NContext("tos.message.action.warning", disable_joke=True))
    warn_template.append(I18NContext("tos.message.action", action=action, disable_joke=True))

    # 上报场景按场景组配置，展开后同一现实场景的多个平台入口只应由其中一个收到回传
    await send_report(
        warn_template,
        subject=str(I18NContext("smtp.report.subject.tos", sender=sender)),
        targets=_report_targets(),
    )


async def abuse_warn_target(msg, reason: str):

    issue_url = CoreConfig.issue_url
    warning_counts = _warning_counts()
    # 没有用户 union 的会话（如主动推送）不存在可警告的对象，直接跳过
    sender_union_info = msg.session_info.sender_union_info
    sender_id = msg.session_info.sender_id
    if warning_counts >= 1 and not msg.check_super_user() and sender_union_info and sender_id:
        await sender_union_info.warn_user()
        warn_template = MessageChain.assign(
            [I18NContext("tos.message.warning"), I18NContext("tos.message.reason", reason=reason)]
        )

        identify_str = f"[{msg.session_info.sender_id} ({msg.session_info.target_id})]"
        if sender_union_info.warns <= warning_counts:
            Logger.info(f"Warn {identify_str} by ToS: abuse ({sender_union_info.warns}/{warning_counts})")
        elif sender_union_info.warns > warning_counts:
            Logger.info(f"Ban {identify_str} by ToS: abuse")
        else:
            Logger.info(f"Warn {identify_str} by ToS: abuse")

        if sender_union_info.warns < warning_counts or sender_union_info.trusted:
            await tos_report(sender_id, msg.session_info.target_id, reason)
            warn_template.append(I18NContext("tos.message.warning.count", current_warns=sender_union_info.warns))
            if not sender_union_info.trusted:
                warn_template.append(I18NContext("tos.message.warning.prompt", warn_counts=warning_counts))
            if sender_union_info.warns <= 2 and issue_url:
                warn_template.append(I18NContext("tos.message.appeal", issue_url=issue_url))
        elif sender_union_info.warns == warning_counts:
            await tos_report(sender_id, msg.session_info.target_id, reason)
            warn_template.append(I18NContext("tos.message.warning.last"))
        elif sender_union_info.warns > warning_counts:
            await sender_union_info.switch_identity(trust=False)
            await tos_report(sender_id, msg.session_info.target_id, reason, banned=True)
            warn_template.append(I18NContext("tos.message.banned"))
            if issue_url:
                warn_template.append(I18NContext("tos.message.appeal", issue_url=issue_url))
        await msg.send_message(warn_template)


async def _temp_ban_check(msg):
    if not _enable_tos():
        return None

    scope_key = sender_scope_key(msg)
    ban_info = temp_ban_counter.get(scope_key)
    if not ban_info or ban_info.is_expired():
        return None

    if msg.check_super_user():
        await remove_temp_ban(scope_key)
        return None

    ban_time = time.time() - ban_info.ts
    remaining = int(_temp_ban_time() - ban_time)

    if not ban_info.get("count", 0):
        ban_info["count"] = 0

    if ban_info["count"] < 2:
        ban_info["count"] += 1
        return Stop(
            message=MessageChain.assign(I18NContext("tos.message.tempbanned", ban_time=remaining)),
            scope=StopScope.MESSAGE,
        )
    if ban_info["count"] <= 3:
        ban_info["count"] += 1
        return Stop(
            message=MessageChain.assign(I18NContext("tos.message.tempbanned.warning", ban_time=remaining)),
            scope=StopScope.MESSAGE,
        )
    # 升级处罚：拒绝决定已经形成，通知失败不得把它丢成"放行"
    await _apply_abuse_safely(msg, "{I18N:tos.message.reason.ignore}")
    return Stop(scope=StopScope.MESSAGE, data={"handled": True, "penalty": True})


async def _msg_counter(msg, command: str, *, candidate_scope: bool = False):
    if not _enable_tos():
        Logger.debug("Tos is disabled, check the configuration if it is not work as expected.")
        return None

    scope = StopScope.CANDIDATE if candidate_scope else StopScope.MESSAGE
    sender_key = sender_scope_key(msg)
    reason = None

    bucket_same = _buckets_same[sender_key][command]
    if "bucket" not in bucket_same:
        bucket_same["bucket"] = TokenBucket(10, 300)
    if not bucket_same["bucket"].consume():
        reason = "{I18N:tos.message.reason.cooldown}"

    if reason is None:
        bucket_all = _buckets_all[sender_key]
        if "bucket" not in bucket_all:
            bucket_all["bucket"] = TokenBucket(20, 300)
        if not bucket_all["bucket"].consume():
            reason = "{I18N:tos.message.reason.abuse}"

    if reason is None:
        return None

    # 超限是已确定的业务拒绝：先固定 Stop，再尽力完成处罚通知，
    # 上报/提示发送失败不得把已确认超限的命令放行。
    await _apply_abuse_safely(msg, reason)
    return Stop(scope=scope, data={"reason": reason, "handled": True})


def _format_reason(msg, reason: str):
    return I18NContext("tos.message.reason", reason=_resolve_reason_text(msg, reason))


async def _send_generic_abuse_error(msg, reason: str):
    err_msg_chain = MessageChain.assign(I18NContext("error.message.prompt"))
    err_msg_chain += _format_reason(msg, reason)
    err_msg_chain.append(I18NContext("error.message.prompt.noreport"))
    await msg.send_message(err_msg_chain)


async def _apply_abuse_safely(msg, reason: str):
    try:
        await _apply_abuse(msg, reason)
    except (Exception, SendMessageFailed, SessionFinished, WaitCancelException):
        # 发送失败等框架控制流继承 BaseException；拒绝已形成，不能让 executor
        # 把通知失败视为检查失败后放行。外部取消与进程退出仍必须传播。
        Logger.exception("Failed to deliver ToS penalty notification; rejection still applies.")


async def _apply_abuse(msg, reason: str):
    if not _enable_tos():
        await _send_generic_abuse_error(msg, reason)
        return
    if _warning_counts() >= 1 and not msg.check_super_user():
        await abuse_warn_target(msg, reason)
        temp_ban_counter[sender_scope_key(msg)] = {"count": 1, "ts": time.time()}
        return
    await _send_generic_abuse_error(msg, reason)


# 强制检查沿用旧 parser 的无超时语义；外部取消仍传播，不能因 hook 超时降级放行。
@tos.hook(point=HookPoint.COMMAND_PREPARE, priority=10, name="temp_ban", server_scope=True, timeout=0)
@_enforce_tos
async def _(ctx: "Bot.ParserHookContext"):
    return await _temp_ban_check(ctx.msg)


@tos.hook(point=HookPoint.COMMAND_BEFORE_PARSE, priority=10, name="counter", server_scope=True, timeout=0)
@_enforce_tos
async def _(ctx: "Bot.ParserHookContext"):
    module_name = ctx.module_name or ctx.command_first_word
    if not module_name:
        return None
    module_obj = ModulesManager.modules.get(module_name)
    if module_obj is not None and module_obj.base:
        return None
    return await _msg_counter(ctx.msg, ctx.msg.trigger_msg)


@tos.hook(point=HookPoint.REGEX_PREPARE, priority=10, name="temp_ban", server_scope=True, timeout=0)
@_enforce_tos
async def _(ctx: "Bot.ParserHookContext"):
    if not ctx.data.get("show_typing", True):
        return None
    return await _temp_ban_check(ctx.msg)


@tos.hook(point=HookPoint.REGEX_BEFORE_EXECUTE, priority=10, name="counter", server_scope=True, timeout=0)
@_enforce_tos
async def _(ctx: "Bot.ParserHookContext"):
    if not ctx.data.get("show_typing", True):
        return None
    if ctx.data.get("base"):
        return None
    return await _msg_counter(ctx.msg, ctx.msg.trigger_msg, candidate_scope=True)


@tos.hook(point=HookPoint.EXECUTION_ERROR, priority=10, name="abuse_warning", server_scope=True)
async def _(ctx: "Bot.ParserHookContext"):
    error = ctx.data.get("error")
    if not isinstance(error, AbuseWarning):
        return None
    if not _enable_tos():
        await _send_generic_abuse_error(ctx.msg, str(error))
        return Handled(data={"reason": str(error), "tos_disabled": True})
    await _apply_abuse(ctx.msg, str(error))
    return Handled(data={"reason": str(error)})


# ---- 具名能力：管理命令 / Client RPC（OneBot 等）使用 ----


@tos.hook("check_temp_ban")
async def _(ctx: "Bot.ModuleHookContext"):
    target = ctx.args.get("target")
    if not target:
        return False
    return await check_temp_ban(target)


@tos.hook("remove_temp_ban")
async def _(ctx: "Bot.ModuleHookContext"):
    target = ctx.args.get("target")
    if target:
        await remove_temp_ban(target)
    return None


@tos.hook("report")
async def _(ctx: "Bot.ModuleHookContext"):
    await tos_report(
        ctx.args.get("sender"),
        ctx.args.get("target"),
        ctx.args.get("reason"),
        banned=bool(ctx.args.get("banned", False)),
    )
    return None


@tos.hook("warning_counts")
async def _(ctx: "Bot.ModuleHookContext") -> int:
    return _warning_counts()


__all__ = [
    "tos",
    "sender_scope_key",
    "check_temp_ban",
    "remove_temp_ban",
    "abuse_warn_target",
    "tos_report",
    "temp_ban_counter",
]
