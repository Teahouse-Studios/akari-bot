from config import Config
from core.builtins import Bot
from database import BotDBUtil

WARNING_COUNTS = Config('tos_warning_counts', 5)


async def warn_target(msg: Bot.MessageSession, reason=None):
    if WARNING_COUNTS >= 1:
        current_warns = int(msg.target.sender_info.query.warns) + 1
        msg.target.sender_info.edit('warns', current_warns)
        warn_template = [msg.locale.t("tos.warning")]
        if reason:
            warn_template.append(msg.locale.t("tos.reason") + reason)
        if current_warns < WARNING_COUNTS:
            warn_template.append(
                msg.locale.t(
                    'tos.warning.count',
                    current_warns=current_warns,
                    warn_counts=WARNING_COUNTS))
        if current_warns <= 2 and Config('issue_url'):
            warn_template.append(msg.locale.t('tos.warning.appeal', issue_url=Config('issue_url')))
        if current_warns == WARNING_COUNTS:
            warn_template.append(msg.locale.t('tos.warning.last'))
        if current_warns > WARNING_COUNTS:
            msg.target.sender_info.edit('isInBlockList', True)
            return None
        await msg.send_message('\n'.join(warn_template))


async def pardon_user(user: str):
    BotDBUtil.SenderInfo(user).edit('warns', 0)


async def warn_user(user: str, count=1):
    current_warns = int(BotDBUtil.SenderInfo(user).query.warns) + count
    BotDBUtil.SenderInfo(user).edit('warns', current_warns)
    if current_warns > WARNING_COUNTS and WARNING_COUNTS >= 1:
        BotDBUtil.SenderInfo(user).edit('isInBlockList', True)
    return current_warns
