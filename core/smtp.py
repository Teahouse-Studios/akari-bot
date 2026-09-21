import asyncio
import smtplib
from datetime import UTC, datetime
from email.message import EmailMessage
from email.utils import format_datetime
from typing import Awaitable, Callable

from core.builtins.message.chain import Chainable, MessageChain
from core.config.base import BaseConfig, CoreConfig, SMTPConfig, SMTPSecretConfig
from core.constants.path import assets_path
from core.exports import exports
from core.i18n import Locale, safe_strftime
from core.logger import Logger

locale = Locale(BaseConfig.default_locale)
LOGO_PATH = assets_path / "akaribot_logo.png"


DirectSender = Callable[[object, Chainable], Awaitable[None]]


def email_report_enabled() -> bool:
    return bool(SMTPConfig.enable_email_report and SMTPConfig.smtp_host and SMTPConfig.smtp_recipients)


def _report_footer(issue_url: str) -> str:
    return locale.t("smtp.report.footer", issue_url=issue_url)


def _report_footer_html(issue_url: str) -> str:
    footer = _report_footer(issue_url)
    if not issue_url:
        return footer
    return footer.replace(issue_url, f'<a href="{issue_url}">{issue_url}</a>')


def _build_email_html(body: str, footer: str) -> str:
    return f"""
    <html>
      <body>
        <div>{body.replace(chr(10), "<br>")}</div>
        <div style="margin-top:24px">
          <img src="cid:akaribot_logo" height="64" alt="AkariBot Logo"><br>
          <span>{safe_strftime(datetime.now(), locale.t_str("{I18N:time.date.format} {I18N:time.time.format}"))}</span>
        </div>
        <div style="margin-top:20px;font-size:12px;color:#808080">{footer}</div>
      </body>
    </html>
    """


def send_email(subject: str, body: str) -> None:
    emailmsg = EmailMessage()

    emailmsg["Date"] = format_datetime(datetime.now(UTC), usegmt=True)
    emailmsg["Subject"] = subject
    emailmsg["From"] = SMTPConfig.smtp_sender or SMTPConfig.smtp_username
    emailmsg["To"] = ", ".join(SMTPConfig.smtp_recipients)

    issue_url = CoreConfig.issue_url
    if issue_url:
        emailmsg["List-Unsubscribe"] = f"<{issue_url}>"

    # 纯文本版本
    emailmsg.set_content(f"{body}\n\n{_report_footer(issue_url)}")

    # HTML版本
    emailmsg.add_alternative(_build_email_html(body, _report_footer_html(issue_url)), subtype="html")

    # 内嵌Logo
    if LOGO_PATH.exists():
        with LOGO_PATH.open("rb") as fp:
            logo_data = fp.read()

        html_part = emailmsg.get_payload()[-1]
        html_part.add_related(logo_data, maintype="image", subtype="png", cid="<akaribot_logo>")

    if SMTPConfig.smtp_ssl:
        with smtplib.SMTP_SSL(SMTPConfig.smtp_host, int(SMTPConfig.smtp_port)) as server:
            if SMTPConfig.smtp_username:
                server.login(SMTPConfig.smtp_username, SMTPSecretConfig.smtp_password)
            server.send_message(emailmsg)
        return

    with smtplib.SMTP(SMTPConfig.smtp_host, int(SMTPConfig.smtp_port)) as server:
        server.ehlo()
        if SMTPConfig.smtp_starttls:
            server.starttls()
        if SMTPConfig.smtp_username:
            server.login(SMTPConfig.smtp_username, SMTPSecretConfig.smtp_password)

        server.send_message(emailmsg)


async def send_report(
    message: Chainable,
    subject: str,
    body: str | None = None,
    direct_sender: DirectSender | None = None,
    targets: list | None = None,
) -> None:
    """将上报发送到 SMTP 邮件或配置的上报场景。"""
    if email_report_enabled():
        subject = f"[AkariBot] {locale.t_str(subject)}"
        if body is None:
            body = MessageChain.assign(message).as_sendable(enable_markdown=False).to_str()
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
