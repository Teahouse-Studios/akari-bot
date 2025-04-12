import re

from core.builtins import Bot, Plain, I18NContext
from core.config import Config
from core.constants.default import issue_url_default
from core.database.models import SenderInfo

report_targets = Config("report_targets", [])
WARNING_COUNTS = Config("tos_warning_counts", 5)


async def warn_target(msg: Bot.MessageSession, reason: str):
    issue_url = Config("issue_url", issue_url_default)
    if WARNING_COUNTS >= 1 and not msg.check_super_user():
        await msg.sender_info.warn_user()
        current_warns = msg.sender_info.warns
        warn_template = [
            I18NContext("tos.message.warning"),
            I18NContext("tos.message.reason", reason=msg.locale.t_str(reason))]
        if current_warns < WARNING_COUNTS or msg.sender_info.trusted:
            await tos_report(msg.target.sender_id, msg.target.target_id, reason)
            warn_template.append(I18NContext("tos.message.warning.count", current_warns=msg.sender_info.warns))
            if not msg.sender_info.trusted:
                warn_template.append(I18NContext("tos.message.warning.prompt", warn_counts=WARNING_COUNTS))
            if msg.sender_info.warns <= 2 and issue_url:
                warn_template.append(I18NContext("tos.message.appeal", issue_url=issue_url))
        elif msg.sender_info.warns == WARNING_COUNTS:
            await tos_report(msg.target.sender_id, msg.target.target_id, reason)
            warn_template.append(I18NContext("tos.message.warning.last"))
        elif msg.sender_info.warns > WARNING_COUNTS:
            await msg.sender_info.switch_identity(trust=False)
            await tos_report(msg.target.sender_id, msg.target.target_id, reason, banned=True)
            warn_template.append(I18NContext("tos.message.banned"))
            if issue_url:
                warn_template.append(I18NContext("tos.message.appeal", issue_url=issue_url))
        await msg.send_message(warn_template)


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
        warn_template = [I18NContext("tos.message.report", sender=sender, target=target, disable_joke=True)]
        warn_template.append(I18NContext("tos.message.reason", reason=reason, disable_joke=True))
        if banned:
            action = "{tos.message.action.blocked}"
        else:
            action = "{tos.message.action.warning}"
        warn_template.append(I18NContext("tos.message.action", action=action, disable_joke=True))

        for target_ in report_targets:
            if f := await Bot.FetchTarget.fetch_target(target_):
                await f.send_direct_message(warn_template)
