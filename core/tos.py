from config import Config
from core.builtins import Bot
from core.utils.i18n import Locale, default_locale
from database import BotDBUtil

report_targets = Config('report_targets', [])
WARNING_COUNTS = Config('tos_warning_counts', 5)


async def warn_target(msg: Bot.MessageSession, reason: str):
    if WARNING_COUNTS >= 1 and not msg.check_super_user():
        current_warns = int(msg.target.sender_info.query.warns) + 1
        msg.target.sender_info.edit('warns', current_warns)
        warn_template = [msg.locale.t("tos.message.warning")]
        i18n_reason = msg.locale.tl_str(reason)
        warn_template.append(msg.locale.t("tos.message.reason") + i18n_reason)
        if current_warns < WARNING_COUNTS:
            await tos_report(msg.target.sender_id, msg.target.target_id, reason)
            warn_template.append(
                msg.locale.t(
                    'tos.message.warning.count',
                    current_warns=current_warns,
                    warn_counts=WARNING_COUNTS))
            if current_warns <= 2 and Config('issue_url', cfg_type=str):
                warn_template.append(msg.locale.t('tos.message.appeal', issue_url=Config('issue_url', cfg_type=str)))
        elif current_warns == WARNING_COUNTS:
            await tos_report(msg.target.sender_id, msg.target.target_id, reason)
            warn_template.append(msg.locale.t('tos.message.warning.last'))
        elif current_warns > WARNING_COUNTS:
            msg.target.sender_info.edit('isInBlockList', True)
            await tos_report(msg.target.sender_id, msg.target.target_id, reason, banned=True)
            warn_template.append(msg.locale.t('tos.message.banned'))
            if Config('issue_url', cfg_type=str):
                warn_template.append(msg.locale.t('tos.message.appeal', issue_url=Config('issue_url', cfg_type=str)))
        await msg.send_message('\n'.join(warn_template))


async def pardon_user(user: str):
    BotDBUtil.SenderInfo(user).edit('warns', 0)


async def warn_user(user: str, count=1):
    current_warns = int(BotDBUtil.SenderInfo(user).query.warns) + count
    BotDBUtil.SenderInfo(user).edit('warns', current_warns)
    if current_warns > WARNING_COUNTS and WARNING_COUNTS >= 1:
        BotDBUtil.SenderInfo(user).edit('isInBlockList', True)
    return current_warns


async def tos_report(sender, target, reason, banned=False):
    locale = Locale(default_locale)
    if report_targets:
        warn_template = [locale.t("tos.message.report", sender=sender, target=target)]
        reason = locale.tl_str(reason)
        warn_template.append(locale.t("tos.message.reason") + reason)
        if banned:
            action = locale.t("tos.message.action.blocked")
        else:
            action = locale.t("tos.message.action.warning")
        warn_template.append(locale.t("tos.message.action") + action)

        for target_ in report_targets:
            if f := await Bot.FetchTarget.fetch_target(target_):
                await f.send_direct_message('\n'.join(warn_template), disable_secret_check=True)
