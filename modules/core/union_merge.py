import string
from datetime import datetime, UTC

from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext, Plain
from core.config.base import CoreConfig
from core.database.models import (
    UNION_SCOPE_SENDER,
    UNION_SCOPE_TARGET,
    SenderUnionInfo,
    StoredData,
    TargetUnionInfo,
    TargetUnionBind,
    collect_union_conflicts,
    get_table_name,
    get_union_module_name,
)
from core.utils.container import ExpiringTempDict
from core.utils.random import Random

BIND_CODE_EXPIRED = 300  # 绑定码有效期（秒）
BIND_CODE_LENGTH = 6
BIND_CODE_ALPHABET = string.ascii_uppercase + string.digits


def generate_code(store: ExpiringTempDict, union_id: str, holder_id: str, extra: dict | None = None) -> str:
    """
    为发起方生成一枚绑定码，同一组同时只保留最新的一枚。

    :param store: 绑定码存储。
    :param union_id: 发起方所属的组 ID。
    :param holder_id: 发起方的平台 ID，用于向对方展示绑定来源。
    :param extra: 随绑定码一并留存的附加信息。
    :return: 绑定码。
    """
    for old_code in [code for code, entry in store.items() if entry.get("union_id") == union_id]:
        store.pop(old_code)

    code = "".join(Random.choices(BIND_CODE_ALPHABET, k=BIND_CODE_LENGTH))
    while code in store:
        code = "".join(Random.choices(BIND_CODE_ALPHABET, k=BIND_CODE_LENGTH))

    store[code] = ExpiringTempDict(
        exp=BIND_CODE_EXPIRED,
        data={"union_id": union_id, "holder_id": holder_id, **(extra or {})},
        root=False,
    )
    return code


def take_code(code: str, stores: tuple[tuple[str, ExpiringTempDict], ...]) -> tuple[str, dict] | None:
    """
    取出并消费一枚绑定码，同时判断它属于哪一个 union 域。

    同一枚绑定码不会同时存在于多个存储中（生成时会查重），因此按 ID 就能唯一定位归属，
    用户不必再自己说明这是哪一类绑定码。

    签发时随码留存的附加信息一律原样带回，调用方各自取用所需的字段。

    :param code: 用户输入的绑定码。
    :param stores: ``(union 域, 存储)`` 的序列，按顺序查找。
    :return: ``(union 域, 绑定码信息)``，无效或已过期时为 None。
    """
    code = code.strip().upper()
    for scope, store in stores:
        entry = store.get(code)
        if entry and "union_id" in entry:
            info = dict(entry.items())
            info.setdefault("target_union_id", None)
            info.setdefault("is_private", False)
            store.pop(code)
            return scope, info
    return None


async def issue_code(
    msg: Bot.MessageSession,
    store: ExpiringTempDict,
    union_id: str,
    holder_id: str,
    prompt_key: str,
    extra: dict | None = None,
    code_key: str = "core.bind.message.code",
) -> None:
    """
    生成绑定码并私信给发起方，随后在当前会话中给出提示。

    绑定码若出现在公开会话中可能被他人取用，因此仅通过私信发送；私信发送失败时连同绑定码一并作废，
    避免其在有效期内被他人试出。

    :param store: 绑定码存储。
    :param union_id: 发起方所属的组 ID。
    :param holder_id: 发起方的平台 ID。
    :param prompt_key: 私信中绑定用法提示的 i18n 键。
    :param extra: 随绑定码一并留存的附加信息。
    :param code_key: 展示绑定码本身的 i18n 键。
    """
    if not msg.session_info.support_private_msg:
        await msg.finish(I18NContext("core.bind.message.code.private.unsupported"))

    generated = generate_code(store, union_id, holder_id, extra)
    sent = await msg.send_private_message(
        [
            I18NContext(code_key, code=generated, disable_joke=True),
            I18NContext(
                prompt_key,
                minute=BIND_CODE_EXPIRED // 60,
                prefix=msg.session_info.prefixes[0],
                code=generated,
                disable_joke=True,
            ),
        ]
    )
    # 平台仅在消息实际投递成功时返回消息 ID，未取得即表示该条私信未送达。
    if not sent:
        store.pop(generated)
        await msg.finish(I18NContext("core.bind.message.code.private.failed"))
    await msg.finish(I18NContext("core.bind.message.code.private.sent"))


def id_lines(ids: list[str]) -> list:
    """
    将 ID 列表逐行展示，ID 不参与文本替换。
    """
    return [Plain(i, disable_joke=True) for i in ids]


async def write_merge_log(new_union: str, scope: str, snapshot: dict) -> None:
    """
    把合并前的快照写入存储，便于人工回溯。

    :param new_union: 合并后新建的组 ID。
    :param scope: union 域。
    :param snapshot: 合并前的双方数据快照。
    """
    stored, _ = await StoredData.get_or_create(stored_key=f"union_merge_log:{new_union}", defaults={"value": []})
    logs = stored.value if isinstance(stored.value, list) else []
    logs.append(
        {
            "timestamp": datetime.now(UTC).isoformat(),
            "new_union": new_union,
            "scope": scope,
            **snapshot,
        }
    )
    stored.value = logs
    await stored.save()


async def choose_conflicts(msg: Bot.MessageSession, conflicts: list[type]) -> set[str]:
    """
    逐个询问模块数据冲突时保留哪一份。

    :param conflicts: 双方都有数据的模块表模型。
    :return: 需要保留发起方数据的表名集合。
    """
    keep_other_tables = set()
    for model in conflicts:
        if not await msg.wait_confirm(
            I18NContext("core.bind.message.conflict.choose", module=get_union_module_name(model))
        ):
            keep_other_tables.add(get_table_name(model))
    return keep_other_tables


def conflict_lines(conflicts: list[type]) -> list:
    """
    冲突模块的提示行，无冲突时为空。
    """
    if not conflicts:
        return []
    return [
        I18NContext(
            "core.bind.message.conflict",
            modules="{I18N:message.delimiter}".join(get_union_module_name(m) for m in conflicts),
        )
    ]


async def plan_sender_merge(initiator: SenderUnionInfo, current: SenderUnionInfo) -> dict:
    """
    收集一次账号组合并所需的信息：双方 ID、冲突模块与待确认的文案。

    与执行分离，是为了让私聊下的「账号组 + 会话组」两次合并能共用一次确认：
    先展示两侧的全部变更再一并执行，避免用户在第二次确认时取消而停在只绑一半的状态。

    :param initiator: 生成绑定码的一方。
    :param current: 输入绑定码的一方。
    :return: 合并计划。
    """
    initiator_ids = await initiator.list_bound_ids()
    current_ids = await current.list_bound_ids()
    conflicts = await collect_union_conflicts(current.union_id, initiator.union_id, scope=UNION_SCOPE_SENDER)

    lines = [
        I18NContext("core.bind.message.self.confirm"),
        I18NContext("core.bind.message.self.confirm.initiator", count=len(initiator_ids)),
        *id_lines(initiator_ids),
        I18NContext("core.bind.message.self.confirm.current", count=len(current_ids)),
        *id_lines(current_ids),
        I18NContext("core.bind.message.self.confirm.inherit"),
    ]
    if CoreConfig.enable_petal:
        lines.append(
            I18NContext(
                "core.bind.message.self.confirm.petal",
                initiator=initiator.petal,
                current=current.petal,
                total=initiator.petal + current.petal,
            )
        )
    lines += conflict_lines(conflicts)

    return {
        "initiator": initiator,
        "current": current,
        "initiator_ids": initiator_ids,
        "current_ids": current_ids,
        "conflicts": conflicts,
        "lines": lines,
    }


async def apply_sender_merge(plan: dict, keep_other_tables: set[str]) -> SenderUnionInfo | None:
    """
    按计划执行账号组合并并记录快照。

    :param plan: :func:`plan_sender_merge` 产出的合并计划。
    :param keep_other_tables: 需要保留发起方数据的表名集合。
    :return: 合并后的新账号组。
    """
    initiator: SenderUnionInfo = plan["initiator"]
    current: SenderUnionInfo = plan["current"]
    snapshot = {
        "keep_ids": plan["initiator_ids"],
        "drop_ids": plan["current_ids"],
        "keep_data": {
            "union_id": initiator.union_id,
            "petal": initiator.petal,
            "warns": initiator.warns,
            "trusted": initiator.trusted,
            "superuser": initiator.superuser,
            "sender_data": initiator.sender_data,
        },
        "drop_data": {
            "union_id": current.union_id,
            "petal": current.petal,
            "warns": current.warns,
            "trusted": current.trusted,
            "superuser": current.superuser,
            "sender_data": current.sender_data,
        },
    }
    merged = await initiator.merge_union(current, keep_other_tables)
    if merged:
        await write_merge_log(merged.union_id, UNION_SCOPE_SENDER, snapshot)
    return merged


async def merge_sender_unions(
    msg: Bot.MessageSession, initiator: SenderUnionInfo, current: SenderUnionInfo
) -> SenderUnionInfo | None:
    """
    走完一次账号组合并：展示继承关系 → 确认 → 逐个处理冲突 → 记录快照 → 合并。

    :param initiator: 生成绑定码的一方。
    :param current: 输入绑定码的一方。
    :return: 合并后的新账号组，用户取消时为 None。
    """
    plan = await plan_sender_merge(initiator, current)
    if not await msg.wait_confirm(plan["lines"]):
        return None
    return await apply_sender_merge(plan, await choose_conflicts(msg, plan["conflicts"]))


async def plan_target_merge(
    initiator: TargetUnionInfo,
    current: TargetUnionInfo,
    inherit_key: str = "core.bind.message.target.confirm.inherit",
) -> dict:
    """
    收集一次会话组合并所需的信息：双方 ID、冲突模块与待确认的文案。

    :param initiator: 发起方（生成绑定码或发起通道握手的一方）。
    :param current: 另一方。
    :param inherit_key: 继承说明的 i18n 键。绑定码流程仅合并会话组，消息通道保持独立；
                        ``bind auto`` 会同时将双方并入同一条消息通道，两者的说明需分开。
    :return: 合并计划。
    """
    initiator_ids = await initiator.list_bound_ids()
    current_ids = await current.list_bound_ids()
    conflicts = await collect_union_conflicts(current.union_id, initiator.union_id, scope=UNION_SCOPE_TARGET)

    lines = [
        I18NContext("core.bind.message.target.confirm"),
        I18NContext("core.bind.message.target.confirm.initiator", count=len(initiator_ids)),
        *id_lines(initiator_ids),
        I18NContext("core.bind.message.target.confirm.current", count=len(current_ids)),
        *id_lines(current_ids),
        I18NContext(inherit_key),
    ]
    lines += conflict_lines(conflicts)

    return {
        "initiator": initiator,
        "current": current,
        "initiator_ids": initiator_ids,
        "current_ids": current_ids,
        "conflicts": conflicts,
        "lines": lines,
    }


async def apply_target_merge(plan: dict, keep_other_tables: set[str]) -> TargetUnionInfo | None:
    """
    按计划执行会话组合并并记录快照。

    :param plan: :func:`plan_target_merge` 产出的合并计划。
    :param keep_other_tables: 需要保留发起方数据的表名集合。
    :return: 合并后的新会话组。
    """
    initiator: TargetUnionInfo = plan["initiator"]
    current: TargetUnionInfo = plan["current"]
    snapshot = {
        "keep_ids": plan["initiator_ids"],
        "drop_ids": plan["current_ids"],
        "keep_data": {
            "union_id": initiator.union_id,
            "locale": initiator.locale,
            "modules": initiator.modules,
            "custom_admins": initiator.custom_admins,
            "banned_users": initiator.banned_users,
            "target_data": initiator.target_data,
        },
        "drop_data": {
            "union_id": current.union_id,
            "locale": current.locale,
            "modules": current.modules,
            "custom_admins": current.custom_admins,
            "banned_users": current.banned_users,
            "target_data": current.target_data,
        },
    }
    merged = await initiator.merge_union(current, keep_other_tables)
    if merged:
        await write_merge_log(merged.union_id, UNION_SCOPE_TARGET, snapshot)
    return merged


async def merge_target_unions(
    msg: Bot.MessageSession,
    initiator: TargetUnionInfo,
    current: TargetUnionInfo,
    inherit_key: str = "core.bind.message.target.confirm.inherit",
) -> TargetUnionInfo | None:
    """
    走完一次会话组合并：展示继承关系 → 确认 → 逐个处理冲突 → 记录快照 → 合并。

    :param initiator: 发起方（生成绑定码或发起通道握手的一方）。
    :param current: 另一方。
    :param inherit_key: 继承说明的 i18n 键。
    :return: 合并后的新会话组，用户取消时为 None。
    """
    plan = await plan_target_merge(initiator, current, inherit_key)
    if not await msg.wait_confirm(plan["lines"]):
        return None
    return await apply_target_merge(plan, await choose_conflicts(msg, plan["conflicts"]))


async def target_lines(union_id: str, ids: list[str]) -> list:
    """
    将会话 ID 逐行展示，每行标注所在的消息通道，末尾附通道含义说明。

    :param union_id: 这些会话所属的组 ID。
    :param ids: 组内的平台会话 ID。
    """
    channels = await TargetUnionBind.list_channels(union_id)
    lines = []
    for target_id in ids:
        channel_id = channels.get(target_id)
        if channel_id is None:
            # 缺少绑定行的会话理论上不会出现在此处，此分支仅作兜底，避免展示流程中断。
            lines.append(Plain(target_id, disable_joke=True))
        else:
            lines.append(
                I18NContext("core.bind.message.target.info.entry", id=target_id, channel=channel_id, disable_joke=True)
            )
    return lines + [I18NContext("core.bind.message.channel.hint")]
