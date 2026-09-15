"""错误和管理消息上报服务。"""

import asyncio
import smtplib
from email.message import EmailMessage
from typing import Awaitable, Callable

from core.builtins.message.chain import Chainable
from core.config.base import CoreConfig, SMTPConfig, SMTPSecretConfig
from core.exports import exports
from core.logger import Logger


DirectSender = Callable[[object, Chainable], Awaitable[None]]


def email_report_enabled() -> bool:
    return bool(SMTPConfig.enable and SMTPConfig.smtp_host and SMTPSecretConfig.smtp_recipients)


def _send_email(subject: str, body: str) -> None:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = SMTPConfig.smtp_sender or SMTPConfig.smtp_username
    message["To"] = ", ".join(SMTPSecretConfig.smtp_recipients)
    message.set_content(body)

    if SMTPConfig.smtp_ssl:
        with smtplib.SMTP_SSL(SMTPConfig.smtp_host, SMTPConfig.smtp_port) as server:
            if SMTPConfig.smtp_username:
                server.login(SMTPConfig.smtp_username, SMTPSecretConfig.smtp_password)
            server.send_message(message)
        return

    with smtplib.SMTP(SMTPConfig.smtp_host, SMTPConfig.smtp_port) as server:
        if SMTPConfig.smtp_starttls:
            server.starttls()
        if SMTPConfig.smtp_username:
            server.login(SMTPConfig.smtp_username, SMTPSecretConfig.smtp_password)
        server.send_message(message)


async def send_report(
    message: Chainable,
    subject: str,
    body: str,
    direct_sender: DirectSender | None = None,
    targets: list | None = None,
) -> None:
    """将上报发送到 SMTP 邮件或配置的上报场景。

    邮件上报配置完整时不会触发任何场景消息；未启用邮件时才使用场景上报。
    """
    if email_report_enabled():
        try:
            await asyncio.to_thread(_send_email, subject, body)
        except Exception:
            Logger.exception("Failed to send report email: ")
        return

    targets = CoreConfig.report_targets if targets is None else targets
    if not targets:
        return

    bot = exports["Bot"]
    sender = direct_sender or (
        lambda target, report: bot.send_direct_message(target, report, disable_secret_check=True)
    )
    for target in await bot.pick_channel_heads(await bot.fetch_union_target_list(targets)):
        await sender(target, message)


__all__ = ["email_report_enabled", "send_report"]
