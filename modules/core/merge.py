import re

from core.builtins.bot import Bot
from core.builtins.message.internal import ActionText, I18NContext
from core.component import module
from core.config.base import CoreConfig
from core.database.models import (
    UNION_SCOPE_SENDER,
    UNION_SCOPE_TARGET,
    SenderUnionInfo,
    TargetUnionInfo,
    TargetUnionBind,
)
from core.retired import RETIRED_SOURCES, RETIRED_TARGETS, enqueue_notice, is_merge_route_allowed
from core.union_merge import (
    BIND_CODE_EXPIRED,
    apply_sender_merge,
    apply_target_merge,
    choose_conflicts,
    id_lines,
    issue_code,
    merge_target_unions,
    plan_sender_merge,
    plan_target_merge,
    take_code,
    target_lines,
)
from core.utils.container import ExpiringTempDict

# 迁移码与 bind 的绑定码分开存放，两者不可互相消费：
# 迁移码用于把退役实例上的数据搬到新实例，与常规的跨平台绑定不是同一件事。
_sender_merge_codes = ExpiringTempDict(exp=BIND_CODE_EXPIRED)
_target_merge_codes = ExpiringTempDict(exp=BIND_CODE_EXPIRED)


def _take_merge_code(code: str) -> tuple[str, dict] | None:
    """
    取出并消费一枚由 ``merge`` 签发的迁移码。

    :param code: 用户输入的迁移码。
    :return: ``(union 域, 迁移码信息)``，无效或已过期时为 None。
    """
    return take_code(
        code,
        ((UNION_SCOPE_SENDER, _sender_merge_codes), (UNION_SCOPE_TARGET, _target_merge_codes)),
    )


async def _unify_channel(initiator_target_id: str, current_target_id: str) -> int:
    """
    把两个场景并入同一条消息通道。

    迁移完成后二者对应同一个现实场景，统一通道号可使命令执行与消息推送只由其中一方承担。
    若日后取消退役、两个机器人回到共作状态，不同通道会让通道认领的快路径判定「通道内仅有自身」
    而双双放行，同一条命令因此被响应两次；统一通道是那条回退路径唯一的保险。

    通道号取发起方的现有编号，发起方缺少绑定行时退回 1。

    :param initiator_target_id: 发起方的场景 ID。
    :param current_target_id: 兑换方的场景 ID。
    :return: 统一后的通道号。
    """
    initiator_bind = await TargetUnionBind.get_or_none(target_id=initiator_target_id)
    channel_id = initiator_bind.channel_id if initiator_bind else 1
    await TargetUnionBind.filter(target_id__in=[initiator_target_id, current_target_id]).update(channel_id=channel_id)
    return channel_id


m = module(
    "merge",
    base=True,
    doc=True,
    suppress_invalid_prompt=True,
    load=bool(CoreConfig.retired_clients),
    desc="{I18N:core.merge.help.desc}",
)


@m.command("{{I18N:core.merge.help}}", available_for=RETIRED_SOURCES)
async def _(msg: Bot.MessageSession):
    session_info = msg.session_info
    # 迁移码须记下签发方的客户端与场景：前者用于兑换时校验迁移去处，
    # 后者用于迁移完成后统一两侧的消息通道号。
    origin = {"source_client": session_info.client_name, "holder_target_id": session_info.target_id}

    if session_info.is_private:
        # 私聊里「这个账号」与「这段私聊」是同一回事，两者一并迁移，
        # 否则用户的个人数据仍留在退役实例上。
        await issue_code(
            msg,
            _sender_merge_codes,
            session_info.sender_union_info.union_id,
            session_info.sender_id,
            "core.merge.message.start.private.prompt",
            extra={
                "target_union_id": session_info.target_union_info.union_id,
                "is_private": True,
                **origin,
            },
            code_key="core.merge.message.code",
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
        "core.merge.message.start.prompt",
        extra={"is_private": False, **origin},
        code_key="core.merge.message.code",
        command="merge token",
    )


async def _merge_private(msg: Bot.MessageSession, entry: dict) -> None:
    """
    完成一次私聊迁移：账号数据与私聊场景数据一并合并。

    私聊里「这个账号」与「这段私聊」指的是同一件事，只并其一会让另一半的数据留在退役实例上。
    两者共用一次确认后一起执行，避免用户在第二次确认时取消而停在只迁一半的状态。

    :param entry: 迁移码携带的发起方信息。
    """
    session_info = msg.session_info
    sender_current = session_info.sender_union_info
    target_current = session_info.target_union_info

    # 签发迁移码的一方为发起方，冲突数据默认以发起方为准。
    sender_initiator = await SenderUnionInfo.get_or_none(union_id=entry["union_id"])
    target_initiator = await TargetUnionInfo.get_or_none(union_id=entry["target_union_id"])
    if not sender_initiator or not target_initiator:
        await msg.finish(
            I18NContext(
                "core.merge.message.code.invalid",
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
        await msg.finish(I18NContext("core.merge.message.same"))

    lines = [I18NContext("core.merge.message.private.confirm")]
    for plan in (sender_plan, target_plan):
        if plan:
            lines += plan["lines"]
    if not await msg.wait_confirm(lines):
        await msg.finish()

    # 冲突选择按域分别询问，两域的模块表互不相交，各自的选择不会互相影响。
    sender_keep = await choose_conflicts(msg, sender_plan["conflicts"]) if sender_plan else set()
    target_keep = await choose_conflicts(msg, target_plan["conflicts"]) if target_plan else set()

    merged_sender = await apply_sender_merge(sender_plan, sender_keep) if sender_plan else sender_current
    merged_target = await apply_target_merge(target_plan, target_keep) if target_plan else target_current
    if not merged_sender or not merged_target:
        await msg.finish(I18NContext("core.merge.message.private.failed"))

    await _unify_channel(entry["holder_target_id"], session_info.target_id)
    await session_info.refresh_info()

    sender_ids = await merged_sender.list_bound_ids()
    target_ids = await merged_target.list_bound_ids()
    await msg.finish(
        [
            I18NContext("core.merge.message.self.success", id=merged_sender.union_id, disable_joke=True),
            I18NContext("core.bind.message.self.info.bound", count=len(sender_ids)),
        ]
        + id_lines(sender_ids)
        + [
            I18NContext("core.merge.message.target.success", id=merged_target.union_id, disable_joke=True),
            I18NContext("core.bind.message.target.info.bound", count=len(target_ids)),
        ]
        + await target_lines(msg, merged_target.union_id, target_ids)
    )


@m.command("token <code> {{I18N:core.merge.help.token}}", available_for=RETIRED_TARGETS)
async def _(msg: Bot.MessageSession, code: str):
    taken = _take_merge_code(code)
    if not taken:
        await msg.finish(
            I18NContext(
                "core.merge.message.code.invalid",
                prefix=msg.session_info.prefixes[0],
                cmd=ActionText(f"{msg.session_info.prefixes[0]}merge"),
            )
        )
    scope, entry = taken

    # 迁移码只能在其所属迁移关系的目标平台兑换。命令级 available_for 只能表明本平台是
    # 某条关系的目标，配置多条关系时挡不住拿甲关系的码来乙关系的目标兑换。
    if not is_merge_route_allowed(entry.get("source_client"), msg.session_info.client_name):
        await msg.finish(I18NContext("core.merge.message.route.mismatch"))

    # 迁移码的签发与使用须处于同类场景：私聊码带着发起方的场景组，若在群里兑换，
    # 会把一段私聊的数据并进群场景；群码在私聊里兑换同理。
    if entry["is_private"] != msg.session_info.is_private:
        await msg.finish(I18NContext("core.merge.message.scene.mismatch"))

    if scope == UNION_SCOPE_SENDER:
        await _merge_private(msg, entry)

    # 场景迁移会改动整个场景的数据，与签发迁移码时一样需要管理员权限。
    if not await msg.check_permission():
        await msg.finish(I18NContext("parser.admin.permission.denied.command"))

    current = msg.session_info.target_union_info
    if entry["union_id"] == current.union_id:
        await msg.finish(I18NContext("core.merge.message.same"))
    initiator = await TargetUnionInfo.get_or_none(union_id=entry["union_id"])
    if not initiator:
        await msg.finish(
            I18NContext(
                "core.merge.message.code.invalid",
                prefix=msg.session_info.prefixes[0],
                cmd=ActionText(f"{msg.session_info.prefixes[0]}merge"),
            )
        )

    merged = await merge_target_unions(msg, initiator, current, "core.merge.message.target.confirm.inherit")
    if not merged:
        await msg.finish()

    channel_id = await _unify_channel(entry["holder_target_id"], msg.session_info.target_id)
    await msg.session_info.refresh_info()

    bound_ids = await merged.list_bound_ids()
    await msg.finish(
        [
            I18NContext("core.merge.message.target.success", id=merged.union_id, disable_joke=True),
            I18NContext("core.bind.message.target.info.bound", count=len(bound_ids)),
        ]
        + await target_lines(msg, merged.union_id, bound_ids)
        + [I18NContext("core.merge.message.channel.unified", channel=channel_id)]
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
    """
    退役公告的触发器。

    只做排队，不向场景发送任何内容：公告由延时任务在数分钟后主动推送，与命令是否被拦截无关。
    若挂在命令拦截上，退役后用户不再发命令，该场景便永远收不到公告；而群内聊天是持续的。

    标记为单次触发，使其对每个场景只跑一次，避免每条消息都付出通道认领的数据库查询与统计插入。
    """
    await enqueue_notice(msg.session_info)
