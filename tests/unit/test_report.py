"""上报服务单元测试。"""

from email.utils import parsedate_to_datetime
from unittest.mock import AsyncMock, MagicMock, patch

from core.config.base import BaseConfig, CoreConfig, SMTPConfig, SMTPSecretConfig
from core.i18n import Locale
from core.smtp import send_email, send_report
from core.tester import Tester, func_case


async def _test_email_takes_priority_over_targets():
    direct_sender = AsyncMock()
    with (
        patch.object(SMTPConfig, "enable_email_report", True),
        patch.object(SMTPConfig, "smtp_host", "smtp.example.com"),
        patch.object(SMTPConfig, "smtp_recipients", ["ops@example.com"]),
        patch("core.smtp.send_email") as send_email,
    ):
        await send_report("message", "subject", "body", direct_sender=direct_sender, targets=["target"])

    return send_email.call_args.args == ("[AkariBot] subject", "body") and not direct_sender.called


async def _test_targets_are_used_without_email():
    direct_sender = AsyncMock()
    bot = MagicMock()
    bot.fetch_union_target_list = AsyncMock(return_value=["target-a", "target-b"])
    bot.pick_channel_heads = AsyncMock(return_value=["target-a"])
    with (
        patch.object(SMTPConfig, "enable_email_report", False),
        patch("core.smtp.exports", {"Bot": bot}),
    ):
        await send_report("message", "subject", "body", direct_sender=direct_sender, targets=["report"])

    return (
        bot.fetch_union_target_list.await_args.args == (["report"],)
        and bot.pick_channel_heads.await_args.args == (["target-a", "target-b"],)
        and direct_sender.await_args.args == ("target-a", "message")
    )


async def _test_no_targets_does_not_send():
    direct_sender = AsyncMock()
    with patch.object(SMTPConfig, "enable_email_report", False):
        await send_report("message", "subject", "body", direct_sender=direct_sender, targets=[])
    return not direct_sender.called


async def _test_external_smtp_client_uses_starttls_and_login():
    smtp = MagicMock()
    smtp_context = smtp.__enter__.return_value
    with (
        patch.object(SMTPConfig, "smtp_host", "smtp.example.com"),
        patch.object(SMTPConfig, "smtp_port", 587),
        patch.object(SMTPConfig, "smtp_sender", "bot@example.com"),
        patch.object(SMTPConfig, "smtp_username", "bot@example.com"),
        patch.object(SMTPConfig, "smtp_starttls", True),
        patch.object(SMTPConfig, "smtp_ssl", False),
        patch.object(SMTPSecretConfig, "smtp_password", "app-password"),
        patch.object(SMTPConfig, "smtp_recipients", ["ops@example.com", "backup@example.com"]),
        patch("core.smtp.smtplib.SMTP", return_value=smtp) as smtp_constructor,
    ):
        send_email("subject", "body")

    message = smtp_context.send_message.call_args.args[0]
    plain_part = message.get_body(preferencelist=("plain",))
    html_part = message.get_body(preferencelist=("html",))
    inline_logo = [part for part in message.walk() if part.get("Content-ID") == "<akaribot_logo>"]
    issue_url = CoreConfig.issue_url
    footer = Locale(BaseConfig.default_locale).t("smtp.report.footer", issue_url=issue_url)
    return (
        smtp_constructor.call_args.args == ("smtp.example.com", 587)
        and smtp_context.ehlo.called
        and smtp_context.starttls.called
        and smtp_context.login.call_args.args == ("bot@example.com", "app-password")
        and message["From"] == "bot@example.com"
        and message["To"] == "ops@example.com, backup@example.com"
        and message["Subject"] == "subject"
        and plain_part.get_content() == f"body\n\n{footer}\n"
        and "body" in html_part.get_content()
        and f'<a href="{issue_url}">{issue_url}</a>' in html_part.get_content()
        and len(inline_logo) == 1
        and inline_logo[0].get_content_type() == "image/png"
        and parsedate_to_datetime(message["Date"]).tzinfo is not None
    )


@func_case
async def test_report(tester: Tester):
    """core.smtp: SMTP 与场景上报路由测试"""
    await tester.test(_test_email_takes_priority_over_targets, "SMTP 优先于场景上报测试")
    await tester.test(_test_targets_are_used_without_email, "未启用 SMTP 时场景上报测试")
    await tester.test(_test_no_targets_does_not_send, "无上报场景时跳过测试")
    await tester.test(_test_external_smtp_client_uses_starttls_and_login, "外部 SMTP 服务商连接测试")
    return tester
