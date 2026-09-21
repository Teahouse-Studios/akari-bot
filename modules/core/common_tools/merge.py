import re

from core.builtins.bot import Bot
from core.builtins.message.internal import ActionText, I18NContext
from core.component import module
from core.config.base import CoreConfig
from core.database.models import (
    UNION_SCOPE_SENDER,
    UNION_SCOPE_TARGET,
    SenderUnionInfo,
    TargetUnionBind,
    TargetUnionInfo,
)
from core.utils.retired import RETIRED_SOURCES, RETIRED_TARGETS, enqueue_notice, is_merge_route_allowed
from core.utils.union_merge import (
    BIND_CODE_EXPIRED,
    apply_sender_merge,
    apply_target_merge,
    choose_conflicts,
    id_lines,
    issue_code,
    merge_target_unions,
    plan_sender_merge,
    plan_target_merge,
    reserve_sender_merge,
    take_code,
    target_lines,
)
from core.utils.container import ExpiringTempDict
from modules.core.common_tools.bind import b

# 迁移码与 bind 的绑定码分开存放，两者不可互相消费：
# 迁移码用于把退役实例上的数据搬到新实例，与常规的跨平台绑定不是同一件事。
_sender_merge_codes = ExpiringTempDict(exp=BIND_CODE_EXPIRED)
_target_merge_codes = ExpiringTempDict(exp=BIND_CODE_EXPIRED)

# 迁移命令已并入 bind（merge 为其别名），此处保留同名隐藏模块，仅承载退役公告触发器：
# 退役策略的白名单按模块名放行，公告正则须挂在白名单模块上才能在退役场景继续匹配。
m = module("merge", base=True, hidden=True, load=bool(CoreConfig.retired_clients))


def _take_merge_code(code: str) -> tuple[str, dict] | None:
    return take_code(
        code,
        ((UNION_SCOPE_SENDER, _sender_merge_codes), (UNION_SCOPE_TARGET, _target_merge_codes)),
    )


async def _unify_channel(initiator_target_id: str, current_target_id: str) -> int:
    channel_id = await TargetUnionInfo.unify_channels(initiator_target_id, current_target_id)
    if channel_id is not None:
        return channel_id

    binds = await TargetUnionBind.filter(target_id__in=[initiator_target_id, current_target_id])
    by_id = {row.target_id: row for row in binds}
    initiator_bind = by_id.get(initiator_target_id)
    current_bind = by_id.get(current_target_id)
    if initiator_bind and current_bind:
        # 两行都存在却无法统一，说明迁移后的 Target Union 拓扑与调用约定不符；
        # 此时不能把其中一侧静默移到其它通道，避免掩盖未完成的 Union 合并。
        raise RuntimeError("Unable to unify migrated target channels.")

    fallback_channel = initiator_bind.channel_id if initiator_bind else 1
    if current_bind and current_bind.channel_id != fallback_channel:
        return await TargetUnionInfo.reassign_channel(current_target_id, fallback_channel) or fallback_channel
    return fallback_channel


@b.command("merge {{I18N:core.help.bind.merge}}", available_for=RETIRED_SOURCES)
async def _(msg: Bot.MessageSession):
    session_info = msg.session_info
    # 迁移码须记下签发方的客户端与场景：前者用于兑换时校验迁移去处，
    # 后者用于迁移完成后统一两侧的消息通道号。
    origin = {"source_client": session_info.client_name, "holder_target_id": session_info.target_id}

    if session_info.is_private:
        # 私聊中的用户身份与私聊场景属于同一数据边界，应一并迁移，
        # 否则用户的个人数据仍留在退役实例上。
        await issue_code(
            msg,
            _sender_merge_codes,
            session_info.sender_union_info.union_id,
            session_info.sender_id,
            "core.message.bind.merge.start.private.prompt",
            extra={
                "target_union_id": session_info.target_union_info.union_id,
                "is_private": True,
                **origin,
            },
            code_key="core.message.bind.merge.code",
            command="merge token",
        )
    # 场景迁移会改动整个场景的数据，需要管理员权限；私聊则无此顾虑，故在此处而非命令级校验。
    if not await msg.check_permission():
        await msg.finish(I18NContext("parser.admin.permission.denied.command"))
    await issue_code(
        msg,
        _target_merge_codes,
        session_info.target_union_info.union_id,
        session_info.target_id,
        "core.message.bind.merge.start.prompt",
        extra={"is_private": False, **origin},
        code_key="core.message.bind.merge.code",
        command="merge token",
    )


async def _merge_private(msg: Bot.MessageSession, entry: dict) -> None:
    session_info = msg.session_info
    sender_current = session_info.sender_union_info
    target_current = session_info.target_union_info

    # 签发迁移码的一方为发起方，冲突数据默认以发起方为准。
    sender_initiator = await SenderUnionInfo.get_or_none(union_id=entry["union_id"])
    target_initiator = await TargetUnionInfo.get_or_none(union_id=entry["target_union_id"])
    if not sender_initiator or not target_initiator:
        await msg.finish(
            I18NContext(
                "core.message.bind.merge.code.invalid",
                prefix=session_info.prefixes[0],
                cmd=ActionText(f"{session_info.prefixes[0]}merge"),
            )
        )

    sender_plan = (
        await plan_sender_merge(sender_initiator, sender_current)
        if sender_initiator.union_id != sender_current.union_id
        else None
    )
    target_plan = (
        await plan_target_merge(msg, target_initiator, target_current)
        if target_initiator.union_id != target_current.union_id
        else None
    )
    if not sender_plan and not target_plan:
        await msg.finish(I18NContext("core.message.bind.merge.same"))

    lines = [I18NContext("core.message.bind.merge.private.confirm")]
    for plan in (sender_plan, target_plan):
        if plan:
            lines += plan["lines"]
    if not await msg.wait_confirm(lines):
        await msg.finish()

    # 场景侧选择须在建立 sender barrier 前完成；普通 wait_confirm 会释放执行
    # lease。sender barrier 建立后，其冲突选择则保持 lease，直到合并写入结束。
    target_keep = await choose_conflicts(msg, target_plan["conflicts"]) if target_plan else set()
    if sender_plan:
        sender_plan = await reserve_sender_merge(msg, sender_plan)
    sender_keep = (
        await choose_conflicts(msg, sender_plan["conflicts"], preserve_execution_lock=True) if sender_plan else set()
    )

    merged_sender = await apply_sender_merge(sender_plan, sender_keep, msg) if sender_plan else sender_current
    merged_target = await apply_target_merge(target_plan, target_keep) if target_plan else target_current
    if not merged_sender or not merged_target:
        await msg.finish(I18NContext("core.message.bind.merge.private.failed"))

    await _unify_channel(entry["holder_target_id"], session_info.target_id)
    await session_info.refresh_info()

    sender_ids = await merged_sender.list_bound_ids()
    target_ids = await merged_target.list_bound_ids()
    await msg.finish(
        [
            I18NContext("core.message.bind.merge.self.success", id=merged_sender.union_id, disable_joke=True),
            I18NContext("core.message.bind.self.info.bound", count=len(sender_ids)),
        ]
        + id_lines(sender_ids)
        + [
            I18NContext("core.message.bind.merge.target.success", id=merged_target.union_id, disable_joke=True),
            I18NContext("core.message.bind.target.info.bound", count=len(target_ids)),
        ]
        + await target_lines(msg, merged_target.union_id, target_ids)
    )


# 命令字面量在解析器中按「位置无关的标志」匹配，再取尾随参数。
# 若沿用 merge token 作为命令路径，源平台上的迁移码会被 bind token 抢先匹配
# （<code> 吞掉 "merge"），源平台将不再让位给新机器人。故取一个不与其冲突的
# 单词；用户侧的命令不变，~merge token <code> 经别名映射到这里。
@b.command("merge-token <code> {{I18N:core.help.bind.merge.token}}", available_for=RETIRED_TARGETS)
async def _(msg: Bot.MessageSession, code: str):
    taken = _take_merge_code(code)
    if not taken:
        await msg.finish(
            I18NContext(
                "core.message.bind.merge.code.invalid",
                cmd=ActionText(f"{msg.session_info.prefixes[0]}merge"),
            )
        )
    scope, entry = taken

    # 迁移码只能在其所属迁移关系的目标平台兑换。命令级 available_for 只能表明本平台是
    # 某条关系的目标，配置多条关系时挡不住拿甲关系的码来乙关系的目标兑换。
    if not is_merge_route_allowed(entry.get("source_client"), msg.session_info.client_name):
        await msg.finish(I18NContext("core.message.bind.merge.route.mismatch"))

    # 迁移码的签发与使用须处于同类场景：私聊码带着发起方的场景组，若在群里兑换，
    # 会把一段私聊的数据并进群场景；群码在私聊里兑换同理。
    if entry["is_private"] != msg.session_info.is_private:
        await msg.finish(I18NContext("core.message.bind.merge.context.mismatch"))

    if scope == UNION_SCOPE_SENDER:
        await _merge_private(msg, entry)

    # 场景迁移会改动整个场景的数据，与签发迁移码时一样需要管理员权限。
    if not await msg.check_permission():
        await msg.finish(I18NContext("parser.admin.permission.denied.command"))

    current = msg.session_info.target_union_info
    if entry["union_id"] == current.union_id:
        await msg.finish(I18NContext("core.message.bind.merge.same"))
    initiator = await TargetUnionInfo.get_or_none(union_id=entry["union_id"])
    if not initiator:
        await msg.finish(
            I18NContext(
                "core.message.bind.merge.code.invalid",
                cmd=ActionText(f"{msg.session_info.prefixes[0]}merge"),
            )
        )

    merged = await merge_target_unions(msg, initiator, current, "core.message.bind.merge.target.confirm.inherit")
    if not merged:
        await msg.finish()

    channel_id = await _unify_channel(entry["holder_target_id"], msg.session_info.target_id)
    await msg.session_info.refresh_info()

    bound_ids = await merged.list_bound_ids()
    await msg.finish(
        [
            I18NContext("core.message.bind.merge.target.success", id=merged.union_id, disable_joke=True),
            I18NContext("core.message.bind.target.info.bound", count=len(bound_ids)),
        ]
        + await target_lines(msg, merged.union_id, bound_ids)
        + [I18NContext("core.message.bind.merge.channel.unified", channel=channel_id)]
    )


@m.regex(
    re.compile(r".+"),
    mode="M",
    show_typing=False,
    logging=False,
    trigger_once_startup=True,
    available_for=RETIRED_SOURCES,
)
async def _(msg: Bot.MessageSession):
    await enqueue_notice(msg.session_info)
