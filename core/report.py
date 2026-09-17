import asyncio
import smtplib
from datetime import UTC, datetime
from email.message import EmailMessage
from email.utils import format_datetime
from typing import Awaitable, Callable

from core.builtins.message.chain import Chainable, MessageChain
from core.config.base import CoreConfig, SMTPConfig, SMTPSecretConfig
from core.constants.path import assets_path
from core.exports import exports
from core.logger import Logger

LOGO_PATH = assets_path / "akaribot_logo.png"


DirectSender = Callable[[object, Chainable], Awaitable[None]]


def email_report_enabled() -> bool:
    return bool(SMTPConfig.enable_email_report and SMTPConfig.smtp_host and SMTPConfig.smtp_recipients)


def _build_email_html(body: str) -> str:
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    return f"""
    <html>
      <body>
        <div>{body.replace(chr(10), '<br>')}</div>
        <div style="margin-top:24px">
          <img src="cid:akari_logo" height="64"><br>
          <span>{date}</span>
        </div>
      </body>
    </html>
    """


def send_email(subject: str, body: str) -> None:
    message = EmailMessage()

    message["Date"] = format_datetime(datetime.now(UTC), usegmt=True)
    message["Subject"] = subject
    message["From"] = SMTPConfig.smtp_sender or SMTPConfig.smtp_username
    message["To"] = ", ".join(SMTPConfig.smtp_recipients)

    # 纯文本版本
    message.set_content(body)

    # HTML版本
    message.add_alternative(_build_email_html(body), subtype="html")

    # 内嵌Logo
    if LOGO_PATH.exists():
        with LOGO_PATH.open("rb") as fp:
            logo_data = fp.read()

        html_part = message.get_payload()[-1]
        html_part.add_related(logo_data, maintype="image", subtype="png", cid="<akari_logo>")

    if SMTPConfig.smtp_ssl:
        with smtplib.SMTP_SSL(SMTPConfig.smtp_host, int(SMTPConfig.smtp_port)) as server:
            if SMTPConfig.smtp_username:
                server.login(SMTPConfig.smtp_username, SMTPSecretConfig.smtp_password)
            server.send_message(message)
        return

    with smtplib.SMTP(SMTPConfig.smtp_host, int(SMTPConfig.smtp_port)) as server:
        server.ehlo()

        if SMTPConfig.smtp_starttls:
            server.starttls()

        if SMTPConfig.smtp_username:
            server.login(SMTPConfig.smtp_username, SMTPSecretConfig.smtp_password)

        server.send_message(message)


async def send_report(
    message: Chainable,
    subject: str,
    body: str | None = None,
    direct_sender: DirectSender | None = None,
    targets: list | None = None,
) -> None:
    """将上报发送到 SMTP 邮件或配置的上报场景。

    邮件上报配置完整时不会触发任何场景消息；未启用邮件时才使用场景上报。
    """
    if email_report_enabled():
        if body is None:
            body = MessageChain.assign(message).as_sendable(disable_markdown=True).to_str()
        try:
            await asyncio.to_thread(send_email, subject, body)
        except Exception:
            Logger.exception("Failed to send report email: ")
        else:
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


__all__ = ["email_report_enabled", "send_email", "send_report"]
