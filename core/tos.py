import time

from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import I18NContext
from core.config.base import CoreConfig
from core.logger import Logger
from core.utils.container import ExpiringTempDict

report_targets = CoreConfig.report_targets
WARNING_COUNTS = CoreConfig.tos_warning_counts
TOS_TEMPBAN_TIME = CoreConfig.tos_temp_ban_time if CoreConfig.tos_temp_ban_time > 0 else 300

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
    issue_url = CoreConfig.issue_url
    # 没有用户 union 的会话（如主动推送）不存在可警告的对象，直接跳过
    sender_union_info = msg.session_info.sender_union_info
    sender_id = msg.session_info.sender_id
    if WARNING_COUNTS >= 1 and not msg.check_super_user() and sender_union_info and sender_id:
        await sender_union_info.warn_user()
        warn_template = MessageChain.assign(
            [I18NContext("tos.message.warning"), I18NContext("tos.message.reason", reason=reason)]
        )

        # Logs
        identify_str = f"[{msg.session_info.sender_id} ({msg.session_info.target_id})]"
        if sender_union_info.warns <= WARNING_COUNTS:
            Logger.info(f"Warn {identify_str} by ToS: abuse ({sender_union_info.warns}/{WARNING_COUNTS})")
        elif sender_union_info.warns > WARNING_COUNTS:
            Logger.info(f"Ban {identify_str} by ToS: abuse")
        else:
            Logger.info(f"Warn {identify_str} by ToS: abuse")

        # Send warns
        if sender_union_info.warns < WARNING_COUNTS or sender_union_info.trusted:
            await tos_report(sender_id, msg.session_info.target_id, reason)
            warn_template.append(I18NContext("tos.message.warning.count", current_warns=sender_union_info.warns))
            if not sender_union_info.trusted:
                warn_template.append(I18NContext("tos.message.warning.prompt", warn_counts=WARNING_COUNTS))
            if sender_union_info.warns <= 2 and issue_url:
                warn_template.append(I18NContext("tos.message.appeal", issue_url=issue_url))
        elif sender_union_info.warns == WARNING_COUNTS:
            await tos_report(sender_id, msg.session_info.target_id, reason)
            warn_template.append(I18NContext("tos.message.warning.last"))
        elif sender_union_info.warns > WARNING_COUNTS:
            await sender_union_info.switch_identity(trust=False)
            await tos_report(sender_id, msg.session_info.target_id, reason, banned=True)
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

        # 上报场景按场景组配置，展开后同一现实场景的多个平台入口只应由其中一个收到回传
        for f in await Bot.pick_channel_heads(await Bot.fetch_union_target_list(report_targets)):
            await Bot.send_direct_message(f, warn_template)
