"""上报服务单元测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

from core.config.base import SMTPConfig, SMTPSecretConfig
from core.report import _send_email, send_report
from core.tester import Tester, func_case


async def _test_email_takes_priority_over_targets():
    """SMTP 配置完整时只发送邮件，不触发场景上报。"""
    direct_sender = AsyncMock()
    with (
        patch.object(SMTPConfig, "enable", True),
        patch.object(SMTPConfig, "smtp_host", "smtp.example.com"),
        patch.object(SMTPSecretConfig, "smtp_recipients", ["ops@example.com"]),
        patch("core.report._send_email") as send_email,
    ):
        await send_report("message", "subject", "body", direct_sender=direct_sender, targets=["target"])

    return send_email.call_args.args == ("subject", "body") and not direct_sender.called


async def _test_targets_are_used_without_email():
    """未启用 SMTP 时发送到传入的上报场景。"""
    direct_sender = AsyncMock()
    bot = MagicMock()
    bot.fetch_union_target_list = AsyncMock(return_value=["target-a", "target-b"])
    bot.pick_channel_heads = AsyncMock(return_value=["target-a"])
    with (
        patch.object(SMTPConfig, "enable", False),
        patch("core.report.exports", {"Bot": bot}),
    ):
        await send_report("message", "subject", "body", direct_sender=direct_sender, targets=["report"])

    return (
        bot.fetch_union_target_list.await_args.args == (["report"],)
        and bot.pick_channel_heads.await_args.args == (["target-a", "target-b"],)
        and direct_sender.await_args.args == ("target-a", "message")
    )


async def _test_no_targets_does_not_send():
    """未启用 SMTP 且没有上报场景时不发送。"""
    direct_sender = AsyncMock()
    with patch.object(SMTPConfig, "enable", False):
        await send_report("message", "subject", "body", direct_sender=direct_sender, targets=[])
    return not direct_sender.called


async def _test_external_smtp_client_uses_starttls_and_login():
    """邮件上报使用外部 SMTP 服务商，并按配置执行 STARTTLS 与登录。"""
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
        patch.object(SMTPSecretConfig, "smtp_recipients", ["ops@example.com", "backup@example.com"]),
        patch("core.report.smtplib.SMTP", return_value=smtp) as smtp_constructor,
    ):
        _send_email("subject", "body")

    message = smtp_context.send_message.call_args.args[0]
    return (
        smtp_constructor.call_args.args == ("smtp.example.com", 587)
        and smtp_context.starttls.called
        and smtp_context.login.call_args.args == ("bot@example.com", "app-password")
        and message["From"] == "bot@example.com"
        and message["To"] == "ops@example.com, backup@example.com"
        and message["Subject"] == "subject"
        and message.get_content() == "body\n"
    )


@func_case
async def test_report(tester: Tester):
    """core.report: SMTP 与场景上报路由测试"""
    await tester.test(_test_email_takes_priority_over_targets, "SMTP 优先于场景上报测试")
    await tester.test(_test_targets_are_used_without_email, "未启用 SMTP 时场景上报测试")
    await tester.test(_test_no_targets_does_not_send, "无上报场景时跳过测试")
    await tester.test(_test_external_smtp_client_uses_starttls_and_login, "外部 SMTP 服务商连接测试")
    return tester
