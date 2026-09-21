"""parser 异常上报的消息格式测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from core.builtins.message.elements import MarkdownElement, PlainElement
from core.i18n import Locale
from core.tester import Tester, func_case


async def _test_exception_report_uses_target_markdown_capability():
    import importlib

    errors = importlib.import_module("modules.core.hooks.errors")

    traceback_text = 'Traceback (most recent call last):\n  File "test.py", line 1\nRuntimeError: failed'
    msg = SimpleNamespace(
        session_info=SimpleNamespace(
            locale=Locale("zh_cn"),
            support_markdown=False,
            support_image=False,
            session_id="error-report-format",
        ),
        trigger_msg="~broken",
        handle_error_signal=AsyncMock(),
        send_message=AsyncMock(),
    )
    report = AsyncMock()
    no_emote = AsyncMock()

    with (
        patch.object(errors.traceback, "format_exc", return_value=traceback_text),
        patch.object(errors, "send_report", report),
        patch.object(errors, "send_common_emote", no_emote),
        patch.object(errors.CoreConfig, "bug_report_url", ""),
        patch.object(errors.CoreConfig, "report_targets", ["report-target"]),
    ):
        await errors.process_exception(msg, RuntimeError("failed"))

    report_message = report.await_args.kwargs["message"]
    markdown = report_message.as_sendable(
        SimpleNamespace(support_embed=False, support_markdown=True, locale=Locale("zh_cn"))
    ).values[1]
    plain = report_message.as_sendable(
        SimpleNamespace(support_embed=False, support_markdown=False, locale=Locale("zh_cn"))
    ).values[1]
    return (
        isinstance(markdown, MarkdownElement)
        and markdown.text == f"```\n{traceback_text}\n```"
        and type(plain) is PlainElement
        and plain.text == traceback_text
        and markdown.disable_joke
        and not markdown.allow_parse
        and plain.disable_joke
        and not plain.allow_parse
    )


@func_case
async def test_error_reporting(tester: Tester):
    """错误上报按目标平台能力渲染 traceback 测试"""
    await tester.test(_test_exception_report_uses_target_markdown_capability, "错误上报 Markdown 呈现测试")
    return tester
