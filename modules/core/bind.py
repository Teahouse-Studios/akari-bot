import asyncio
import string
from datetime import datetime, UTC

from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext, Plain
from core.component import module
from core.config.base import CoreConfig
from core.database.models import (
    UNION_SCOPE_SENDER,
    UNION_SCOPE_TARGET,
    SenderInfo,
    StoredData,
    TargetInfo,
    TargetUnionBind,
    collect_union_conflicts,
    get_table_name,
    get_union_module_name,
)
from core.utils.container import ExpiringTempDict
from core.utils.func import is_int
from core.utils.random import Random

BIND_CODE_EXPIRED = 300  # 绑定码有效期（秒）
BIND_CODE_LENGTH = 6
BIND_CODE_ALPHABET = string.ascii_uppercase + string.digits

HANDSHAKE_EXPIRED = 30  # 通道握手超时（秒）
HANDSHAKE_TOKEN_LENGTH = 20

# 绑定码与握手状态仅保存在 server 进程内存中，重启即失效。
# 各平台的 bot 子进程共用同一个 server 进程，因此跨平台握手无需落库。
_sender_bind_codes = ExpiringTempDict(exp=BIND_CODE_EXPIRED)
_target_bind_codes = ExpiringTempDict(exp=BIND_CODE_EXPIRED)
_channel_handshakes = {}
# 握手闭合串行执行。若让位机制未生效（如某一平台的 probe 投递延迟），
# 两轮并发执行至「是否同组」判定时会同时读到合并前的数据，各自新建一个组，合并即告失败。
_handshake_lock = asyncio.Lock()


def _generate_code(store: ExpiringTempDict, union_id: str, holder_id: str) -> str:
    """
    为发起方生成一枚绑定码，同一组同时只保留最新的一枚。

    :param store: 绑定码存储。
    :param union_id: 发起方所属的组 ID。
    :param holder_id: 发起方的平台 ID，用于向对方展示绑定来源。
    :return: 绑定码。
    """
    for old_code in [code for code, entry in store.items() if entry.get("union_id") == union_id]:
        store.pop(old_code)

    code = "".join(Random.choices(BIND_CODE_ALPHABET, k=BIND_CODE_LENGTH))
    while code in store:
        code = "".join(Random.choices(BIND_CODE_ALPHABET, k=BIND_CODE_LENGTH))

    store[code] = ExpiringTempDict(
        exp=BIND_CODE_EXPIRED,
        data={"union_id": union_id, "holder_id": holder_id},
        root=False,
    )
    return code


def _take_code(code: str) -> tuple[str, dict] | None:
    """
    取出并消费一枚绑定码，同时判断它属于账号组还是会话组。

    两个存储里不可能同时存在同一枚绑定码（生成时会查重），因此按 ID 就能唯一定位归属，
    用户不必再自己说明这是账号绑定码还是会话绑定码。

    :param code: 用户输入的绑定码。
    :return: ``(union 域, 绑定码信息)``，无效或已过期时为 None。
    """
    code = code.strip().upper()
    for scope, store in ((UNION_SCOPE_SENDER, _sender_bind_codes), (UNION_SCOPE_TARGET, _target_bind_codes)):
        entry = store.get(code)
        if entry and "union_id" in entry:
            info = {"union_id": entry.get("union_id"), "holder_id": entry.get("holder_id")}
            store.pop(code)
            return scope, info
    return None


async def _issue_bind_code(
    msg: Bot.MessageSession, store: ExpiringTempDict, union_id: str, holder_id: str, prompt_key: str
) -> None:
    """
    生成绑定码并私信给发起方，随后在当前会话中给出提示。

    绑定码若出现在公开会话中可能被他人取用，因此仅通过私信发送；私信发送失败时连同绑定码一并作废，
    避免其在有效期内被他人试出。

    :param store: 绑定码存储。
    :param union_id: 发起方所属的组 ID。
    :param holder_id: 发起方的平台 ID。
    :param prompt_key: 私信中绑定用法提示的 i18n 键。
    """
    if not msg.session_info.support_private_msg:
        await msg.finish(I18NContext("core.bind.message.code.private.unsupported"))

    generated = _generate_code(store, union_id, holder_id)
    sent = await msg.send_private_message(
        [
            I18NContext("core.bind.message.code", code=generated, disable_joke=True),
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


def _id_lines(ids: list[str]) -> list:
    """
    将 ID 列表逐行展示，ID 不参与文本替换。
    """
    return [Plain(i, disable_joke=True) for i in ids]


async def _write_merge_log(new_union: str, scope: str, snapshot: dict) -> None:
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


async def _choose_conflicts(msg: Bot.MessageSession, conflicts: list[type]) -> set[str]:
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


def _conflict_lines(conflicts: list[type]) -> list:
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


async def _merge_sender_unions(
    msg: Bot.MessageSession, initiator: SenderInfo, current: SenderInfo
) -> SenderInfo | None:
    """
    走完一次账号组合并：展示继承关系 → 确认 → 逐个处理冲突 → 记录快照 → 合并。

    :param initiator: 生成绑定码的一方。
    :param current: 输入绑定码的一方。
    :return: 合并后的新账号组，用户取消时为 None。
    """
    initiator_ids = await initiator.list_bound_ids()
    current_ids = await current.list_bound_ids()
    conflicts = await collect_union_conflicts(current.union_id, initiator.union_id, scope=UNION_SCOPE_SENDER)

    confirm_msg = [
        I18NContext("core.bind.message.self.confirm"),
        I18NContext("core.bind.message.self.confirm.initiator", count=len(initiator_ids)),
        *_id_lines(initiator_ids),
        I18NContext("core.bind.message.self.confirm.current", count=len(current_ids)),
        *_id_lines(current_ids),
        I18NContext("core.bind.message.self.confirm.inherit"),
    ]
    if CoreConfig.enable_petal:
        confirm_msg.append(
            I18NContext(
                "core.bind.message.self.confirm.petal",
                initiator=initiator.petal,
                current=current.petal,
                total=initiator.petal + current.petal,
            )
        )
    confirm_msg += _conflict_lines(conflicts)

    if not await msg.wait_confirm(confirm_msg):
        return None

    keep_other_tables = await _choose_conflicts(msg, conflicts)
    snapshot = {
        "keep_ids": initiator_ids,
        "drop_ids": current_ids,
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
        await _write_merge_log(merged.union_id, UNION_SCOPE_SENDER, snapshot)
    return merged


async def _merge_target_unions(
    msg: Bot.MessageSession,
    initiator: TargetInfo,
    current: TargetInfo,
    inherit_key: str = "core.bind.message.target.confirm.inherit",
) -> TargetInfo | None:
    """
    走完一次会话组合并：展示继承关系 → 确认 → 逐个处理冲突 → 记录快照 → 合并。

    :param initiator: 发起方（生成绑定码或发起通道握手的一方）。
    :param current: 另一方。
    :param inherit_key: 继承说明的 i18n 键。绑定码流程仅合并会话组，消息通道保持独立；
                        ``bind auto`` 会同时将双方并入同一条消息通道，两者的说明需分开。
    :return: 合并后的新会话组，用户取消时为 None。
    """
    initiator_ids = await initiator.list_bound_ids()
    current_ids = await current.list_bound_ids()
    conflicts = await collect_union_conflicts(current.union_id, initiator.union_id, scope=UNION_SCOPE_TARGET)

    confirm_msg = [
        I18NContext("core.bind.message.target.confirm"),
        I18NContext("core.bind.message.target.confirm.initiator", count=len(initiator_ids)),
        *_id_lines(initiator_ids),
        I18NContext("core.bind.message.target.confirm.current", count=len(current_ids)),
        *_id_lines(current_ids),
        I18NContext(inherit_key),
    ]
    confirm_msg += _conflict_lines(conflicts)

    if not await msg.wait_confirm(confirm_msg):
        return None

    keep_other_tables = await _choose_conflicts(msg, conflicts)
    snapshot = {
        "keep_ids": initiator_ids,
        "drop_ids": current_ids,
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
        await _write_merge_log(merged.union_id, UNION_SCOPE_TARGET, snapshot)
    return merged


async def _target_lines(union_id: str, ids: list[str]) -> list:
    """
    将会话 ID 逐行展示，每行标注所在的消息通道，末尾附通道含义说明。

    :param union_id: 这些会话所属的组 ID。
    :param ids: 组内的平台会话 ID。
    """
    channels = await TargetInfo.list_channels_by_union(union_id)
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


async def _channel_lines(msg: Bot.MessageSession) -> list:
    """
    当前会话的消息通道信息，含同通道的其它会话。
    """
    bind = getattr(msg.session_info.target_info, "_bind", None)
    if not bind:
        return [I18NContext("core.bind.message.channel.unknown")]

    channels = await TargetInfo.list_channels_by_union(bind.union_id)
    siblings = [target_id for target_id, channel_id in channels.items() if channel_id == bind.channel_id]
    return [
        I18NContext("core.bind.message.channel.info", channel=bind.channel_id),
        I18NContext("core.bind.message.channel.info.shared", count=len(siblings)),
        *_id_lines(siblings),
        I18NContext("core.bind.message.channel.hint"),
    ]


b = module("bind", base=True, desc="{I18N:core.bind.help.desc}", doc=True, alias="uid")


@b.command("{{I18N:core.bind.help}}")
async def _(msg: Bot.MessageSession):
    sender_info = msg.session_info.sender_info
    target_info = msg.session_info.target_info
    sender_ids = await sender_info.list_bound_ids()
    target_ids = await target_info.list_bound_ids()
    await msg.finish(
        [
            I18NContext("core.bind.message.self.info", id=sender_info.union_id, disable_joke=True),
            I18NContext("core.bind.message.self.info.bound", count=len(sender_ids)),
        ]
        + _id_lines(sender_ids)
        + [
            I18NContext("core.bind.message.target.info", id=target_info.union_id, disable_joke=True),
            I18NContext("core.bind.message.target.info.bound", count=len(target_ids)),
        ]
        + await _target_lines(target_info.union_id, target_ids)
    )


@b.command("self {{I18N:core.bind.help.self}}")
async def _(msg: Bot.MessageSession):
    sender_info = msg.session_info.sender_info
    bound_ids = await sender_info.list_bound_ids()
    await msg.finish(
        [
            I18NContext("core.bind.message.self.info", id=sender_info.union_id, disable_joke=True),
            I18NContext("core.bind.message.self.info.bound", count=len(bound_ids)),
        ]
        + _id_lines(bound_ids)
    )


@b.command("self start {{I18N:core.bind.help.self.start}}")
async def _(msg: Bot.MessageSession):
    await _issue_bind_code(
        msg,
        _sender_bind_codes,
        msg.session_info.sender_info.union_id,
        msg.session_info.sender_id,
        "core.bind.message.self.code.prompt",
    )


@b.command("self remove <user> {{I18N:core.bind.help.self.remove}}")
async def _(msg: Bot.MessageSession, user: str):
    sender_info = msg.session_info.sender_info
    bound_ids = await sender_info.list_bound_ids()
    if user not in bound_ids:
        await msg.finish(I18NContext("core.bind.message.self.remove.not_bound"))
    if len(bound_ids) <= 1:
        await msg.finish(I18NContext("core.bind.message.self.remove.last"))
    if not await msg.wait_confirm(I18NContext("core.bind.message.self.remove.confirm", id=user, disable_joke=True)):
        await msg.finish()
    if not await sender_info.unbind_id(user):
        await msg.finish(I18NContext("core.bind.message.self.remove.failed"))
    await msg.session_info.refresh_info()
    await msg.finish(I18NContext("core.bind.message.self.remove.success", id=user, disable_joke=True))


@b.command("target {{I18N:core.bind.help.target}}", required_admin=True)
async def _(msg: Bot.MessageSession):
    target_info = msg.session_info.target_info
    bound_ids = await target_info.list_bound_ids()
    await msg.finish(
        [
            I18NContext("core.bind.message.target.info", id=target_info.union_id, disable_joke=True),
            I18NContext("core.bind.message.target.info.bound", count=len(bound_ids)),
        ]
        + await _target_lines(target_info.union_id, bound_ids)
    )


@b.command("target start {{I18N:core.bind.help.target.start}}", required_admin=True)
async def _(msg: Bot.MessageSession):
    await _issue_bind_code(
        msg,
        _target_bind_codes,
        msg.session_info.target_info.union_id,
        msg.session_info.target_id,
        "core.bind.message.target.code.prompt",
    )


@b.command("target remove <target> {{I18N:core.bind.help.target.remove}}", required_admin=True)
async def _(msg: Bot.MessageSession, target: str):
    target_info = msg.session_info.target_info
    bound_ids = await target_info.list_bound_ids()
    if target not in bound_ids:
        await msg.finish(I18NContext("core.bind.message.target.remove.not_bound"))
    if len(bound_ids) <= 1:
        await msg.finish(I18NContext("core.bind.message.target.remove.last"))
    if not await msg.wait_confirm(I18NContext("core.bind.message.target.remove.confirm", id=target, disable_joke=True)):
        await msg.finish()
    if not await target_info.unbind_id(target):
        await msg.finish(I18NContext("core.bind.message.target.remove.failed"))
    await msg.session_info.refresh_info()
    await msg.finish(I18NContext("core.bind.message.target.remove.success", id=target, disable_joke=True))


@b.command("token <code> {{I18N:core.bind.help.token}}")
async def _(msg: Bot.MessageSession, code: str):
    taken = _take_code(code)
    if not taken:
        await msg.finish(I18NContext("core.bind.message.code.invalid"))
    scope, entry = taken

    if scope == UNION_SCOPE_SENDER:
        current = msg.session_info.sender_info
        if entry["union_id"] == current.union_id:
            await msg.finish(I18NContext("core.bind.message.self.same"))
        # 生成绑定码的一方为发起方，冲突数据默认以发起方为准。
        initiator = await SenderInfo.get_or_none(union_id=entry["union_id"])
        if not initiator:
            await msg.finish(I18NContext("core.bind.message.code.invalid"))

        merged = await _merge_sender_unions(msg, initiator, current)
        if not merged:
            await msg.finish()
        await msg.session_info.refresh_info()
        bound_ids = await merged.list_bound_ids()
        await msg.finish(
            [
                I18NContext("core.bind.message.self.success", id=merged.union_id, disable_joke=True),
                I18NContext("core.bind.message.self.info.bound", count=len(bound_ids)),
            ]
            + _id_lines(bound_ids)
        )

    # 会话组绑定会改动整个会话的数据，与 target start 一样需要管理员权限。
    if not await msg.check_permission():
        await msg.finish(I18NContext("parser.admin.permission.denied.command"))

    current = msg.session_info.target_info
    if entry["union_id"] == current.union_id:
        await msg.finish(I18NContext("core.bind.message.target.same"))
    initiator = await TargetInfo.get_or_none(union_id=entry["union_id"])
    if not initiator:
        await msg.finish(I18NContext("core.bind.message.code.invalid"))

    merged = await _merge_target_unions(msg, initiator, current)
    if not merged:
        await msg.finish()
    await msg.session_info.refresh_info()
    bound_ids = await merged.list_bound_ids()
    await msg.finish(
        [
            I18NContext("core.bind.message.target.success", id=merged.union_id, disable_joke=True),
            I18NContext("core.bind.message.target.info.bound", count=len(bound_ids)),
        ]
        + await _target_lines(merged.union_id, bound_ids)
    )


@b.command("channel {{I18N:core.bind.help.channel}}", required_admin=True)
async def _(msg: Bot.MessageSession):
    await msg.finish(await _channel_lines(msg))


@b.command("channel set <channel> {{I18N:core.bind.help.channel.set}}", required_admin=True)
async def _(msg: Bot.MessageSession, channel: str):
    if not is_int(channel) or int(channel) < 1:
        await msg.finish(I18NContext("core.bind.message.channel.set.invalid"))
    bind = getattr(msg.session_info.target_info, "_bind", None)
    if not bind:
        await msg.finish(I18NContext("core.bind.message.channel.unknown"))

    await TargetUnionBind.filter(target_id=msg.session_info.target_id).update(channel_id=int(channel))
    # 变更通道后与原同通道会话不再对应同一个现实会话，保留互认记录会阻碍后续重新配对。
    await msg.session_info.target_info.forget_peer_bots(msg.session_info.target_id)
    await msg.session_info.refresh_info()
    await msg.finish([I18NContext("core.bind.message.channel.set.success", channel=int(channel))])


@b.command("channel reset {{I18N:core.bind.help.channel.reset}}", required_admin=True)
async def _(msg: Bot.MessageSession):
    bind = getattr(msg.session_info.target_info, "_bind", None)
    if not bind:
        await msg.finish(I18NContext("core.bind.message.channel.unknown"))

    channel_id = await TargetInfo.next_channel_id(bind.union_id)
    await TargetUnionBind.filter(target_id=msg.session_info.target_id).update(channel_id=channel_id)
    # 脱离通道后与原同通道会话不再关联，须一并清除互认记录，否则重新配对时握手口令会被双方屏蔽。
    await msg.session_info.target_info.forget_peer_bots(msg.session_info.target_id)
    await msg.session_info.refresh_info()
    await msg.finish(I18NContext("core.bind.message.channel.reset.success", channel=channel_id))


@b.command("auto {{I18N:core.bind.help.auto}}", required_admin=True)
async def _(msg: Bot.MessageSession):
    # 此处不作二次确认：双方尚未关联，通道去重与互认记录均未生效，
    # 同一会话内的每个机器人都会各自解析该命令，确认提示会被重复发出。
    # 需要管理员确认的是握手闭合后的合并提示，该提示已完整说明数据的继承方式。
    probe_token = Random.randstr(HANDSHAKE_TOKEN_LENGTH)
    confirm_token = Random.randstr(HANDSHAKE_TOKEN_LENGTH)
    _channel_handshakes[probe_token] = {"confirm_token": confirm_token, "initiator": msg}

    # 该命令仅由同一会话内的其它机器人识别，对用户而言只是一串无意义的口令。
    await msg.send_message(Plain(f"{msg.session_info.prefixes[0]}bind channel probe {probe_token}"))
    await msg.hold()

    async def _timeout():
        await asyncio.sleep(HANDSHAKE_EXPIRED)
        entry = _channel_handshakes.pop(probe_token, None)
        if entry and not entry.get("done"):
            await msg.send_message(I18NContext("core.bind.message.auto.timeout"))
            await msg.release()

    asyncio.create_task(_timeout())


@b.command("channel probe <token> {{I18N:core.bind.help.channel.internal}}")
async def _(msg: Bot.MessageSession, token: str):
    entry = _channel_handshakes.get(token)
    if not entry:
        await msg.finish()
    initiator: Bot.MessageSession = entry["initiator"]
    # 部分平台会将机器人自身发出的消息回送，遇到自身发起的握手直接忽略。
    if initiator.session_info.target_id == msg.session_info.target_id:
        await msg.finish()

    # 同一会话内的每个机器人都会收到同一条 ~bind auto 并各自发起一轮握手，两轮交叉配对
    # 会使同一对会话被合并两次。此处按 probe 口令排序作确定性让位，仅保留口令最小的一轮。
    # 各方均先登记记录再发出 probe，因此收到对方 probe 时自身记录必然已存在，判定不会遗漏。
    mine = next(
        (
            probe_token
            for probe_token, pending in _channel_handshakes.items()
            if pending["initiator"].session_info.target_id == msg.session_info.target_id
        ),
        None,
    )
    if mine:
        if mine < token:
            # 自身这一轮口令更小，由对方响应本轮即可，不再应答对方。
            await msg.finish()
        yielded = _channel_handshakes.pop(mine, None)
        if yielded:
            await yielded["initiator"].release()

    entry["responder"] = msg
    entry["initiator_bot_id"] = msg.session_info.sender_id
    await msg.send_message(Plain(f"{msg.session_info.prefixes[0]}bind channel confirm {entry['confirm_token']}"))
    await msg.hold()


@b.command("channel confirm <token> {{I18N:core.bind.help.channel.internal}}")
async def _(msg: Bot.MessageSession, token: str):
    for probe_token, entry in _channel_handshakes.copy().items():
        if entry.get("confirm_token") != token or not entry.get("responder"):
            continue
        entry["done"] = True
        _channel_handshakes.pop(probe_token, None)
        entry["responder_bot_id"] = msg.session_info.sender_id
        await _complete_channel_handshake(entry)
        return
    await msg.finish()


async def _complete_channel_handshake(entry: dict) -> None:
    """
    握手闭合后把两个会话合成同一条消息通道。

    此时已确认两个会话对应同一个现实会话，随后执行三项操作：合并会话组（数据共享）、
    统一消息通道号（命令与推送去重）、互相记录对方的机器人账号（屏蔽对方发出的消息）。

    :param entry: 握手记录，含双方的会话与机器人账号。
    """
    initiator: Bot.MessageSession = entry["initiator"]
    responder: Bot.MessageSession = entry["responder"]
    try:
        # 取得锁之后再读取组信息：若先读后锁，读到的仍是并发方修改前的数据，加锁将失去意义。
        async with _handshake_lock:
            await initiator.session_info.refresh_info()
            await responder.session_info.refresh_info()
            initiator_target = initiator.session_info.target_info
            responder_target = responder.session_info.target_info

            initiator_bind = await TargetUnionBind.get_or_none(target_id=initiator.session_info.target_id)
            responder_bind = await TargetUnionBind.get_or_none(target_id=responder.session_info.target_id)
            if (
                initiator_target.union_id == responder_target.union_id
                and initiator_bind
                and responder_bind
                and initiator_bind.channel_id == responder_bind.channel_id
            ):
                # 另一轮握手已完成同样的处理，无需重复向管理员确认，也无需重复写库。
                return

            await _run_channel_handshake(entry, initiator, responder)
    finally:
        await initiator.release()
        await responder.release()


async def _run_channel_handshake(entry: dict, initiator: Bot.MessageSession, responder: Bot.MessageSession) -> None:
    """
    合并会话组、统一通道号、互记机器人账号。调用方需持有 :data:`_handshake_lock`。
    """
    initiator_target = initiator.session_info.target_info
    responder_target = responder.session_info.target_info

    merged = initiator_target
    if initiator_target.union_id != responder_target.union_id:
        # 合并确认在发起侧进行：执行该命令的管理员位于发起侧。
        merged = await _merge_target_unions(
            initiator, initiator_target, responder_target, "core.bind.message.auto.confirm.inherit"
        )
        if not merged:
            await initiator.send_message(I18NContext("core.bind.message.auto.cancelled"))
            return

    # 将对方并入本会话所在的通道，此后二者同组同号，命令执行与消息推送均只由其中一方承担。
    initiator_bind = await TargetUnionBind.get_or_none(target_id=initiator.session_info.target_id)
    channel_id = initiator_bind.channel_id if initiator_bind else 1
    await TargetUnionBind.filter(
        target_id__in=[initiator.session_info.target_id, responder.session_info.target_id]
    ).update(channel_id=channel_id)

    # 记录双方的机器人账号，避免将对方发出的消息当作用户输入解析。
    # 账号按观察方所在平台的命名空间记录：发起方观察到的对端账号取自 confirm，对端观察到的发起方账号取自 probe。
    initiator_id = initiator.session_info.target_id
    responder_id = responder.session_info.target_id
    await merged.link_peer_bots(
        {
            initiator_id: {responder_id: entry.get("responder_bot_id")},
            responder_id: {initiator_id: entry.get("initiator_bot_id")},
        }
    )

    for session in (initiator, responder):
        await session.session_info.refresh_info()
        await session.send_message(
            I18NContext(
                "core.bind.message.auto.success",
                id=merged.union_id,
                channel=channel_id,
                disable_joke=True,
            )
        )
