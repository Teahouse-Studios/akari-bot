import re

from core.builtins import Bot
from core.config import Config
from core.constants.default import issue_url_default
from core.database_v2.models import SenderInfo
from core.utils.i18n import Locale

report_targets = Config("report_targets", [])
WARNING_COUNTS = Config("tos_warning_counts", 5)
default_locale = Config("default_locale", cfg_type=str)


async def warn_target(msg: Bot.MessageSession, reason: str):
    if WARNING_COUNTS >= 1 and not msg.check_super_user():
        await msg.sender_info.warn_user()
        current_warns = await msg.sender_info.warns
        warn_template = [msg.locale.t("tos.message.warning")]
        warn_template.append(msg.locale.t("tos.message.reason") + msg.locale.t_str(reason))
        if current_warns < WARNING_COUNTS or msg.info.is_in_allow_list:
            await tos_report(msg.target.sender_id, msg.target.target_id, reason)
            warn_template.append(
                msg.locale.t("tos.message.warning.count", current_warns=msg.sender_info.warns)
            )
            if not msg.sender_info.trusted:
                warn_template.append(
                    msg.locale.t(
                        "tos.message.warning.prompt", warn_counts=WARNING_COUNTS
                    )
                )
            if msg.sender_info.warns <= 2 and Config(
                "issue_url", issue_url_default, cfg_type=str
            ):
                warn_template.append(
                    msg.locale.t(
                        "tos.message.appeal",
                        issue_url=Config("issue_url", issue_url_default, cfg_type=str),
                    )
                )
        elif msg.sender_info.warns == WARNING_COUNTS:
            await tos_report(msg.target.sender_id, msg.target.target_id, reason)
            warn_template.append(msg.locale.t("tos.message.warning.last"))
        elif msg.sender_info.warns > WARNING_COUNTS:
            await msg.sender_info.switch_identity(trust=False)
            await tos_report(
                msg.target.sender_id, msg.target.target_id, reason, banned=True
            )
            warn_template.append(msg.locale.t("tos.message.banned"))
            if Config("issue_url", issue_url_default, cfg_type=str):
                warn_template.append(
                    msg.locale.t(
                        "tos.message.appeal",
                        issue_url=Config("issue_url", issue_url_default, cfg_type=str),
                    )
                )
        await msg.send_message("\n".join(warn_template))


async def pardon_user(user: str):
    sender_info = (await SenderInfo.get_or_create(sender_id=user))[0]
    await sender_info.edit_attr("warns", 0)


async def warn_user(user: str, count: int = 1):
    sender_info = (await SenderInfo.get_or_create(sender_id=user))[0]
    await sender_info.warn_user(count)
    if sender_info.warns > WARNING_COUNTS >= 1 and not sender_info.trusted:
        await sender_info.switch_identity(trust=False)
    return sender_info.warns


async def tos_report(sender: str, target: str, reason: str, banned: bool = False):
    if report_targets:
        warn_template = [f"[I18N:tos.message.report,sender={sender},target={target}]"]
        reason = re.sub(r"\{([^}]+)\}", lambda match: f"[I18N:{match.group(1)}]", reason)
        warn_template.append("[I18N:tos.message.reason]" + reason)
        if banned:
            action = "[I18N:tos.message.action.blocked]"
        else:
            action = "[I18N:tos.message.action.warning]"
        warn_template.append("[I18N:tos.message.action]" + action)

        for target_ in report_targets:
            if f := await Bot.FetchTarget.fetch_target(target_):
                await f.send_direct_message(
                    "\n".join(warn_template), disable_secret_check=True
                )
