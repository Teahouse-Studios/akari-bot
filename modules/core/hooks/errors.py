"""parser 执行异常的默认用户反馈与报告策略。"""

from __future__ import annotations

import re
import traceback
from pathlib import Path
from typing import TYPE_CHECKING

from core.builtins.message.chain import MessageChain, match_kecode
from core.builtins.message.internal import Image, I18NContext, Markdown, Plain
from core.builtins.parser.hooks import HookPoint
from core.component import module
from core.config.base import CoreConfig
from core.constants.exceptions import (
    AbuseWarning,
    ExternalException,
    InvalidHelpDocTypeError,
    NoReportException,
    SendMessageFailed,
)
from core.constants.path import assets_path
from core.logger import Logger
from core.smtp import send_report
from core.utils.random import Random

if TYPE_CHECKING:
    from core.builtins.bot import Bot


errors = module("parser_errors", hidden=True, load=True, base=True)

COMMON_EMOTE_DIR = assets_path / "emotes" / "common"
INVALID_COMMAND_EMOTES = tuple(sorted((COMMON_EMOTE_DIR / "invalid").glob("*.gif")))
BUG_EMOTES = tuple(sorted((COMMON_EMOTE_DIR / "bug").glob("*.gif")))


async def send_common_emote(msg: "Bot.MessageSession", emotes: tuple[Path, ...]) -> None:
    if not CoreConfig.use_emote or not msg.session_info.support_image or not emotes:
        return
    try:
        await msg.send_message(Image(Random.choice(emotes)), quote=False)
    except (SendMessageFailed, Exception):
        Logger.warning(f"Failed to send common emote in session {msg.session_info.session_id}.")


def format_error_detail(msg_or_session, text: str) -> MessageChain:
    """按目标平台能力格式化错误详情。支持 Markdown 时使用 fenced code block。"""
    session_info = getattr(msg_or_session, "session_info", msg_or_session)
    if not session_info.support_markdown:
        return match_kecode(text)

    return format_error_detail_markdown(text)


def format_error_detail_markdown(text: str) -> MessageChain:
    longest_fence = max((len(match.group(0)) for match in re.finditer(r"`+", text)), default=0)
    fence = "`" * max(3, longest_fence + 1)
    return MessageChain.assign(Markdown(f"{fence}\n{text}\n{fence}", disable_joke=True, allow_parse=False))


async def process_send_message_failed(msg: "Bot.MessageSession") -> None:
    await msg.handle_error_signal()
    await msg.send_message(I18NContext("error.message.limited"))


async def process_abuse_generic_error(msg: "Bot.MessageSession", error: AbuseWarning) -> None:
    err_msg_chain = MessageChain.assign(I18NContext("error.message.prompt"))
    err_msg_chain += match_kecode(msg.session_info.locale.t_str(str(error)))
    err_msg_chain.append(I18NContext("error.message.prompt.noreport"))
    await msg.send_message(err_msg_chain)


async def process_noreport_exception(msg: "Bot.MessageSession", error: NoReportException) -> None:
    Logger.exception()
    err_msg_chain = MessageChain.assign(I18NContext("error.message.prompt"))
    err_msg_chain += format_error_detail(msg, msg.session_info.locale.t_str(str(error)))
    err_msg_chain.append(I18NContext("error.message.prompt.noreport"))
    await msg.handle_error_signal()
    await msg.send_message(err_msg_chain)
    await send_common_emote(msg, BUG_EMOTES)


async def process_external_exception(msg: "Bot.MessageSession", error: Exception) -> None:
    Logger.exception()
    err_msg_chain = MessageChain.assign(I18NContext("error.message.prompt"))
    err_msg_chain += format_error_detail(msg, msg.session_info.locale.t_str(str(error)))
    err_msg_chain.append(I18NContext("error.message.prompt.external"))
    if CoreConfig.bug_report_url:
        err_msg_chain.append(I18NContext("error.message.prompt.address", url=CoreConfig.bug_report_url))
    await msg.handle_error_signal()
    await msg.send_message(err_msg_chain)
    await send_common_emote(msg, BUG_EMOTES)


async def process_exception(msg: "Bot.MessageSession", error: Exception) -> None:
    tb = traceback.format_exc()
    Logger.error(tb)

    err_msg_chain = MessageChain.assign(I18NContext("error.message.prompt"))
    err_msg_chain += format_error_detail(msg, msg.session_info.locale.t_str(str(error)))
    err_msg_chain.append(I18NContext("error.message.prompt.report"))
    if CoreConfig.bug_report_url:
        err_msg_chain.append(I18NContext("error.message.prompt.address", url=CoreConfig.bug_report_url))

    await msg.handle_error_signal()
    await msg.send_message(err_msg_chain)
    await send_common_emote(msg, BUG_EMOTES)
    await send_report(
        message=MessageChain.assign(I18NContext("error.message.report", disable_joke=True, command=msg.trigger_msg))
        + format_error_detail_markdown(tb.strip()),
        subject=str(I18NContext("smtp.report.subject.error.command", cmd=msg.trigger_msg)),
        targets=CoreConfig.report_targets,
    )


@errors.hook(point=HookPoint.EXECUTION_ERROR, priority=100, name="default_feedback", server_scope=True, timeout=0)
async def _execution_error(ctx: "Bot.ParserHookContext"):
    error = ctx.data.get("error")
    # SendMessageFailed 继承 BaseException，是消息会话控制流的一部分，不能用
    # ``Exception`` 作为入口过滤，否则发送失败会被 parser 误记为未处理异常。
    if not isinstance(error, (BaseException,)):
        return None
    if isinstance(error, SendMessageFailed):
        await process_send_message_failed(ctx.msg)
    elif isinstance(error, AbuseWarning):
        await process_abuse_generic_error(ctx.msg, error)
    elif isinstance(error, ExternalException) or ctx.data.get("error_kind") == "external":
        await process_external_exception(ctx.msg, error)
    elif isinstance(error, NoReportException):
        await process_noreport_exception(ctx.msg, error)
    elif isinstance(error, InvalidHelpDocTypeError):
        Logger.exception()
        await ctx.msg.send_message(I18NContext("error.module.helpdoc_invalid", module=ctx.module_name or ""))
        await send_common_emote(ctx.msg, BUG_EMOTES)
    else:
        await process_exception(ctx.msg, error)
    return ctx.Handled()


@errors.hook("format_error_detail")
async def _format_error_detail_hook(ctx: "Bot.ModuleHookContext") -> MessageChain:
    text = ctx.args.get("text", "")
    if not ctx.session_info.support_markdown:
        return MessageChain.assign(Plain(str(text), disable_joke=True, allow_parse=False))
    return format_error_detail(ctx.session_info, str(text))


__all__ = [
    "errors",
    "INVALID_COMMAND_EMOTES",
    "BUG_EMOTES",
    "send_common_emote",
]
