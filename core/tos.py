import time

from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import I18NContext
from core.config import Config
from core.constants.default import issue_url_default
from core.logger import Logger
from core.utils.temp import ExpiringTempDict

report_targets = Config("report_targets", [])
WARNING_COUNTS = Config("tos_warning_counts", 5)
TOS_TEMPBAN_TIME = Config("tos_temp_ban_time", 300) if Config("tos_temp_ban_time", 300) > 0 else 300

temp_ban_counter = ExpiringTempDict(exp=TOS_TEMPBAN_TIME)  # 临时封禁计数


async def check_temp_ban(target):
    ban_info = temp_ban_counter.get(target)
    if ban_info:
        ban_time_remain = int(TOS_TEMPBAN_TIME - (time.time() - ban_info.ts))
        return ban_time_remain
    return False


async def remove_temp_ban(target):
    if await check_temp_ban(target):
        del temp_ban_counter[target]


async def abuse_warn_target(msg: Bot.MessageSession, reason: str):
    issue_url = Config("issue_url", issue_url_default)
    if WARNING_COUNTS >= 1 and not msg.check_super_user():
        await msg.session_info.sender_info.warn_user()
        warn_template = MessageChain.assign([I18NContext("tos.message.warning"),
                                             I18NContext("tos.message.reason", reason=reason)])

        # Logs
        identify_str = f"[{msg.session_info.sender_id} ({msg.session_info.target_id})]"
        if msg.session_info.sender_info.warns <= WARNING_COUNTS:
            Logger.info(f"Warn {identify_str} by ToS: abuse ({msg.session_info.sender_info.warns}/{WARNING_COUNTS})")
        elif msg.session_info.sender_info.warns > WARNING_COUNTS:
            Logger.info(f"Ban {identify_str} by ToS: abuse")
        else:
            Logger.info(f"Warn {identify_str} by ToS: abuse")

        # Send warns
        if msg.session_info.sender_info.warns < WARNING_COUNTS or msg.session_info.sender_info.trusted:
            await tos_report(msg.session_info.sender_id, msg.session_info.target_id, reason)
            warn_template.append(
                I18NContext(
                    "tos.message.warning.count",
                    current_warns=msg.session_info.sender_info.warns))
            if not msg.session_info.sender_info.trusted:
                warn_template.append(I18NContext("tos.message.warning.prompt", warn_counts=WARNING_COUNTS))
            if msg.session_info.sender_info.warns <= 2 and issue_url:
                warn_template.append(I18NContext("tos.message.appeal", issue_url=issue_url))
        elif msg.session_info.sender_info.warns == WARNING_COUNTS:
            await tos_report(msg.session_info.sender_id, msg.session_info.target_id, reason)
            warn_template.append(I18NContext("tos.message.warning.last"))
        elif msg.session_info.sender_info.warns > WARNING_COUNTS:
            await msg.session_info.sender_info.switch_identity(trust=False)
            await tos_report(msg.session_info.sender_id, msg.session_info.target_id, reason, banned=True)
            warn_template.append(I18NContext("tos.message.banned"))
            if issue_url:
                warn_template.append(I18NContext("tos.message.appeal", issue_url=issue_url))
        await msg.send_message(warn_template)


async def tos_report(sender: str, target: str, reason: str, banned: bool = False):
    if report_targets:
        warn_template = [I18NContext("tos.message.report", sender=sender, target=target, disable_joke=True)]
        warn_template.append(I18NContext("tos.message.reason", reason=reason, disable_joke=True))
        if banned:
            action = "{I18N:tos.message.action.blocked}"
        else:
            action = "{I18N:tos.message.action.warning}"
        warn_template.append(I18NContext("tos.message.action", action=action, disable_joke=True))

        for target_ in report_targets:
            if f := await Bot.fetch_target(target_):
                await Bot.send_direct_message(f, warn_template)
