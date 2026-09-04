import asyncio

from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext, Plain
from core.config.base import CoreConfig
from core.component import module
from core.database.models import (
    UNION_SCOPE_SENDER,
    UNION_SCOPE_TARGET,
    SenderUnionInfo,
    TargetUnionInfo,
    TargetUnionBind,
)
from core.logger import Logger
from core.server.lifecycle import BackgroundTaskLifecycle
from core.utils.container import ExpiringTempDict
from core.utils.random import SecureRandom
from core.utils.union_merge import (
    BIND_CODE_EXPIRED,
    apply_sender_merge,
    apply_target_merge,
    channel_hint_lines,
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

HANDSHAKE_EXPIRED = 30  # 通道握手超时（秒）
HANDSHAKE_TOKEN_LENGTH = 20

# 自动配对为多个机器人共处同一场景的情形预留，默认关闭。命令是否注册在导入时即已确定，
# 因此取一份快照，改动配置须重启机器人方能生效。
ENABLE_BIND_AUTO = CoreConfig.enable_bind_auto

# 绑定码与握手状态仅保存在 server 进程内存中，重启即失效。
# 各平台的 bot 子进程共用同一个 server 进程，因此跨平台握手无需落库。
_sender_bind_codes = ExpiringTempDict(exp=BIND_CODE_EXPIRED)
_target_bind_codes = ExpiringTempDict(exp=BIND_CODE_EXPIRED)
# 握手分两段登记：待认领的 probe 与待闭合的 confirm。口令一经发出即出现在场景中，
# 任何人都能原样复制，故两段各自的口令都只能被消费一次。
_pending_probes = globals().get("_pending_probes", {})
_pending_confirms = globals().get("_pending_confirms", {})
# 握手闭合串行执行。若让位机制未生效（如某一平台的 probe 投递延迟），
# 两轮并发执行至「是否同组」判定时会同时读到合并前的数据，各自新建一个组，合并即告失败。
_handshake_lock = globals().get("_handshake_lock") or asyncio.Lock()
# reload 会复用模块字典。保留旧任务与 pending 状态，使重载前创建的超时任务仍能完成清理。
_handshake_tasks: set[asyncio.Task] = globals().get("_handshake_tasks", set())


def _handshake_task_done(task: asyncio.Task) -> None:
    """Drop a finished expiry task and explicitly retrieve its exception."""
    _handshake_tasks.discard(task)
    if task.cancelled():
        return
    error = task.exception()
    if error is not None:
        Logger.error(f"Bind handshake background task {task.get_name()!r} failed: {error!r}")


def _create_handshake_task(awaitable, *, name: str) -> asyncio.Task:
    """Create and retain one handshake lifecycle task."""
    try:
        task = asyncio.create_task(awaitable, name=name)
    except BaseException:
        if hasattr(awaitable, "close"):
            awaitable.close()
        raise
    _handshake_tasks.add(task)
    task.add_done_callback(_handshake_task_done)
    return task


async def _release_sessions(*sessions: Bot.MessageSession) -> None:
    """Best-effort release for every held handshake context, even when one release fails."""
    unique_sessions = []
    seen = set()
    for session in sessions:
        if session is not None and id(session) not in seen:
            seen.add(id(session))
            unique_sessions.append(session)
    results = await asyncio.gather(*(session.release() for session in unique_sessions), return_exceptions=True)
    for result in results:
        if isinstance(result, BaseException):
            Logger.error(f"Failed to release bind handshake context: {result!r}")


async def cancel_bind_handshake_tasks() -> None:
    """Cancel expiry tasks and release every context still owned by an unfinished handshake."""
    current = asyncio.current_task()
    tasks = {task for task in _handshake_tasks if task is not current and not task.done()}
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

    sessions = [entry.get("initiator") for entry in _pending_probes.values()]
    for entry in _pending_confirms.values():
        sessions.extend((entry.get("initiator"), entry.get("responder")))
    _pending_probes.clear()
    _pending_confirms.clear()
    await _release_sessions(*sessions)


def _take_code(code: str) -> tuple[str, dict] | None:
    """
    取出并消费一枚由 ``bind`` 签发的绑定码。

    :param code: 用户输入的绑定码。
    :return: ``(union 域, 绑定码信息)``，无效或已过期时为 None。
    """
    return take_code(
        code,
        ((UNION_SCOPE_SENDER, _sender_bind_codes), (UNION_SCOPE_TARGET, _target_bind_codes)),
    )


async def _channel_lines(msg: Bot.MessageSession) -> list:
    """
    当前场景的消息通道信息，含同通道的其它场景。
    """
    union_id = msg.session_info.target_union_id
    if not union_id:
        return [I18NContext("core.message.bind.channel.unknown")]
    channel_id = msg.session_info.target_channel_id

    channels = await TargetUnionBind.list_channels(union_id)
    siblings = [target_id for target_id, cid in channels.items() if cid == channel_id]
    return [
        I18NContext("core.message.bind.channel.info", channel=channel_id),
        I18NContext("core.message.bind.channel.info.shared", count=len(siblings)),
        *id_lines(siblings),
        *channel_hint_lines(msg),
    ]


b = module(
    "bind",
    base=True,
    desc="{I18N:core.help.bind.desc}",
    doc=True,
    alias={"connect": "bind auto"} if ENABLE_BIND_AUTO else None,
)


@b.command("{{I18N:core.help.bind}}")
async def _(msg: Bot.MessageSession):
    sender_union_info = msg.session_info.sender_union_info
    target_union_info = msg.session_info.target_union_info
    sender_ids = await sender_union_info.list_bound_ids()
    target_ids = await target_union_info.list_bound_ids()
    await msg.finish(
        [
            I18NContext("core.message.bind.self.info", id=sender_union_info.union_id, disable_joke=True),
            I18NContext("core.message.bind.self.info.bound", count=len(sender_ids)),
        ]
        + id_lines(sender_ids)
        + [
            I18NContext("core.message.bind.target.info", id=target_union_info.union_id, disable_joke=True),
            I18NContext("core.message.bind.target.info.bound", count=len(target_ids)),
        ]
        + await target_lines(msg, target_union_info.union_id, target_ids)
    )


@b.command("self {{I18N:core.help.bind.self}}")
async def _(msg: Bot.MessageSession):
    sender_union_info = msg.session_info.sender_union_info
    bound_ids = await sender_union_info.list_bound_ids()
    await msg.finish(
        [
            I18NContext("core.message.bind.self.info", id=sender_union_info.union_id, disable_joke=True),
            I18NContext("core.message.bind.self.info.bound", count=len(bound_ids)),
        ]
        + id_lines(bound_ids)
    )


@b.command("start {{I18N:core.help.bind.start}}")
async def _(msg: Bot.MessageSession):
    session_info = msg.session_info
    if session_info.is_private:
        # 私聊中的用户身份与私聊场景属于同一数据边界，应一并绑定，
        # 否则换个平台私聊机器人时数据仍是两份。
        await issue_code(
            msg,
            _sender_bind_codes,
            session_info.sender_union_info.union_id,
            session_info.sender_id,
            "core.message.bind.start.private.prompt",
            extra={"target_union_id": session_info.target_union_info.union_id, "is_private": True},
        )
    # 场景组绑定会改动整个场景的数据，需要管理员权限；私聊则无此顾虑，故在此处而非命令级校验。
    if not await msg.check_permission():
        await msg.finish(I18NContext("parser.admin.permission.denied.command"))
    await issue_code(
        msg,
        _target_bind_codes,
        session_info.target_union_info.union_id,
        session_info.target_id,
        "core.message.bind.target.code.prompt",
        extra={"is_private": False},
    )


@b.command("self remove <user> {{I18N:core.help.bind.self.remove}}")
async def _(msg: Bot.MessageSession, user: str):
    sender_union_info = msg.session_info.sender_union_info
    bound_ids = await sender_union_info.list_bound_ids()
    if user not in bound_ids:
        await msg.finish(I18NContext("core.message.bind.self.remove.not_bound"))
    if len(bound_ids) <= 1:
        await msg.finish(I18NContext("core.message.bind.self.remove.last"))
    if not await msg.wait_confirm(I18NContext("core.message.bind.self.remove.confirm", id=user, disable_joke=True)):
        await msg.finish()
    if not await sender_union_info.unbind_id(user):
        await msg.finish(I18NContext("core.message.bind.self.remove.failed"))
    await msg.session_info.refresh_info()
    await msg.finish(I18NContext("core.message.bind.self.remove.success", id=user, disable_joke=True))


@b.command("target {{I18N:core.help.bind.target}}", required_admin=True)
async def _(msg: Bot.MessageSession):
    target_union_info = msg.session_info.target_union_info
    bound_ids = await target_union_info.list_bound_ids()
    await msg.finish(
        [
            I18NContext("core.message.bind.target.info", id=target_union_info.union_id, disable_joke=True),
            I18NContext("core.message.bind.target.info.bound", count=len(bound_ids)),
        ]
        + await target_lines(msg, target_union_info.union_id, bound_ids)
    )


@b.command("target remove <target> {{I18N:core.help.bind.target.remove}}", required_admin=True)
async def _(msg: Bot.MessageSession, target: str):
    target_union_info = msg.session_info.target_union_info
    bound_ids = await target_union_info.list_bound_ids()
    if target not in bound_ids:
        await msg.finish(I18NContext("core.message.bind.target.remove.not_bound"))
    if len(bound_ids) <= 1:
        await msg.finish(I18NContext("core.message.bind.target.remove.last"))
    if not await msg.wait_confirm(I18NContext("core.message.bind.target.remove.confirm", id=target, disable_joke=True)):
        await msg.finish()
    if not await target_union_info.unbind_id(target):
        await msg.finish(I18NContext("core.message.bind.target.remove.failed"))
    await msg.session_info.refresh_info()
    await msg.finish(I18NContext("core.message.bind.target.remove.success", id=target, disable_joke=True))


async def _bind_private(msg: Bot.MessageSession, entry: dict) -> None:
    """
    完成一次私聊绑定：账号组与场景组一并合并。

    私聊里「这个账号」与「这段私聊」指的是同一件事，只并其一会让另一半的数据留在原处。
    两者共用一次确认后一起执行，避免用户在第二次确认时取消而停在只绑一半的状态。

    :param entry: 绑定码携带的发起方信息。
    """
    session_info = msg.session_info
    sender_current = session_info.sender_union_info
    target_current = session_info.target_union_info

    # 生成绑定码的一方为发起方，冲突数据默认以发起方为准。
    sender_initiator = await SenderUnionInfo.get_or_none(union_id=entry["union_id"])
    target_initiator = await TargetUnionInfo.get_or_none(union_id=entry["target_union_id"])
    if not sender_initiator or not target_initiator:
        await msg.finish(I18NContext("core.message.bind.code.invalid"))

    # 任一侧已同组则只并另一侧；两侧都已同组说明这枚码来自本方，无需绑定。
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
        await msg.finish(I18NContext("core.message.bind.self.same"))

    lines = [I18NContext("core.message.bind.start.private.confirm")]
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
        await msg.finish(I18NContext("core.message.bind.start.private.failed"))

    await session_info.refresh_info()
    sender_ids = await merged_sender.list_bound_ids()
    target_ids = await merged_target.list_bound_ids()
    await msg.finish(
        [
            I18NContext("core.message.bind.self.success", id=merged_sender.union_id, disable_joke=True),
            I18NContext("core.message.bind.self.info.bound", count=len(sender_ids)),
        ]
        + id_lines(sender_ids)
        + [
            I18NContext("core.message.bind.target.success", id=merged_target.union_id, disable_joke=True),
            I18NContext("core.message.bind.target.info.bound", count=len(target_ids)),
        ]
        + await target_lines(msg, merged_target.union_id, target_ids)
    )


@b.command("token <code> {{I18N:core.help.bind.token}}")
async def _(msg: Bot.MessageSession, code: str):
    taken = _take_code(code)
    if not taken:
        await msg.finish(I18NContext("core.message.bind.code.invalid"))
    scope, entry = taken

    # 绑定码的生成与使用须处于同类场景：私聊码带着发起方的场景组，若在群里兑换，
    # 会把一个群的数据并进对方的私聊；群码在私聊里兑换同理。
    if entry["is_private"] != msg.session_info.is_private:
        await msg.finish(I18NContext("core.message.bind.code.scene.mismatch"))

    if scope == UNION_SCOPE_SENDER:
        await _bind_private(msg, entry)

    # 场景组绑定会改动整个场景的数据，与 bind start 一样需要管理员权限。
    if not await msg.check_permission():
        await msg.finish(I18NContext("parser.admin.permission.denied.command"))

    current = msg.session_info.target_union_info
    if entry["union_id"] == current.union_id:
        await msg.finish(I18NContext("core.message.bind.target.same"))
    initiator = await TargetUnionInfo.get_or_none(union_id=entry["union_id"])
    if not initiator:
        await msg.finish(I18NContext("core.message.bind.code.invalid"))

    merged = await merge_target_unions(msg, initiator, current)
    if not merged:
        await msg.finish()
    await msg.session_info.refresh_info()
    bound_ids = await merged.list_bound_ids()
    await msg.finish(
        [
            I18NContext("core.message.bind.target.success", id=merged.union_id, disable_joke=True),
            I18NContext("core.message.bind.target.info.bound", count=len(bound_ids)),
        ]
        + await target_lines(msg, merged.union_id, bound_ids)
    )


@b.command("channel {{I18N:core.help.bind.channel}}", required_admin=True)
async def _(msg: Bot.MessageSession):
    await msg.finish(await _channel_lines(msg))


@b.command("channel set <channel> {{I18N:core.help.bind.channel.set}}", required_admin=True)
async def _(msg: Bot.MessageSession, channel: int):
    if not msg.session_info.target_union_id:
        await msg.finish(I18NContext("core.message.bind.channel.unknown"))

    assigned_channel = await TargetUnionInfo.reassign_channel(msg.session_info.target_id, int(channel))
    if assigned_channel is None:
        await msg.finish(I18NContext("core.message.bind.channel.unknown"))
    await msg.session_info.refresh_info()
    await msg.finish([I18NContext("core.message.bind.channel.set.success", channel=assigned_channel)])


@b.command("channel reset {{I18N:core.help.bind.channel.reset}}", required_admin=True)
async def _(msg: Bot.MessageSession):
    union_id = msg.session_info.target_union_id
    if not union_id:
        await msg.finish(I18NContext("core.message.bind.channel.unknown"))

    channel_id = await TargetUnionInfo.reassign_channel(msg.session_info.target_id)
    if channel_id is None:
        await msg.finish(I18NContext("core.message.bind.channel.unknown"))
    await msg.session_info.refresh_info()
    await msg.finish(I18NContext("core.message.bind.channel.reset.success", channel=channel_id))


async def _start_handshake(msg: Bot.MessageSession) -> None:
    """
    发起一轮通道握手：登记一枚待认领的 probe 口令并在场景中发出。

    此处不作二次确认：双方尚未关联，通道去重与互认记录均未生效，
    同一场景内的每个机器人都会各自解析该命令，确认提示会被重复发出。
    需要管理员确认的是握手闭合后的合并提示，该提示已完整说明数据的继承方式。
    """
    probe_token = SecureRandom.randstr(HANDSHAKE_TOKEN_LENGTH)
    _pending_probes[probe_token] = {"initiator": msg}

    held = False
    try:
        await msg.hold()
        held = True
        # 该命令仅供同一场景内的其它机器人识别，对用户不具备可读语义。
        await msg.send_message(Plain(f"{msg.session_info.prefixes[0]}bind channel probe {probe_token}"))
        _create_handshake_task(_expire_handshake(probe_token, msg), name=f"bind-handshake-{probe_token}")
    except BaseException:
        _pending_probes.pop(probe_token, None)
        if held:
            await _release_sessions(msg)
        raise


async def _expire_handshake(probe_token: str, initiator: Bot.MessageSession) -> None:
    """
    口令过期后收回本轮握手的全部登记。

    :param probe_token: 本轮的 probe 口令。
    :param initiator: 发起本轮握手的会话。
    """
    await asyncio.sleep(HANDSHAKE_EXPIRED)
    if not _pending_probes.pop(probe_token, None):
        # 本轮已让位或已闭合，上下文在各自的路径中释放，此处不再重复处理。
        return

    # probe 口令既已过期，由它换来的 confirm 口令不应继续有效。
    responders = []
    for confirm_token, pending in _pending_confirms.copy().items():
        if pending["probe_token"] == probe_token:
            _pending_confirms.pop(confirm_token, None)
            responders.append(pending["responder"])

    try:
        await initiator.send_message(I18NContext("core.message.bind.auto.timeout"))
    finally:
        await _release_sessions(*responders, initiator)


async def _respond_probe(msg: Bot.MessageSession, token: str) -> None:
    """
    认领一枚 probe 口令，并换发一枚仅对本次配对有效的 confirm 口令。

    口令在场景中以明文出现，任何人都能原样复制，因此认领是一次性的：口令一经认领即作废，
    其后携带同一串口令的消息一律丢弃。否则复制粘贴该命令的用户会被当作对端机器人记录下来，
    此后其发言都将被视为另一个机器人的输出而遭忽略。

    :param token: 对方发出的 probe 口令。
    """
    entry = _pending_probes.get(token)
    if not entry or entry.get("claimed"):
        await msg.finish()
    initiator: Bot.MessageSession = entry["initiator"]
    # 部分平台会将机器人自身发出的消息回送，遇到自身发起的握手直接忽略。
    if initiator.session_info.target_id == msg.session_info.target_id:
        await msg.finish()

    # 同一场景内的每个机器人都会收到同一条 ~bind auto 并各自发起一轮握手，两轮交叉配对
    # 会使同一对场景被合并两次。此处按 probe 口令排序作确定性让位，仅保留口令最小的一轮。
    # 各方均先登记记录再发出 probe，因此收到对方 probe 时自身记录必然已存在，判定不会遗漏。
    mine = next(
        (
            probe_token
            for probe_token, pending in _pending_probes.items()
            if pending["initiator"].session_info.target_id == msg.session_info.target_id
        ),
        None,
    )
    if mine:
        if mine < token:
            # 自身这一轮口令更小，由对方响应本轮即可，不再应答对方。
            await msg.finish()
        if _pending_probes[mine].get("claimed"):
            # 自身这一轮已被对方认领并等待闭合，无须再另起一轮。
            await msg.finish()
        yielded = _pending_probes.pop(mine, None)
        if yielded:
            await _release_sessions(yielded["initiator"])

    # 让位过程中让出过控制权，其间该口令可能已被另一个机器人认领，认领前须再确认一次。
    if entry.get("claimed"):
        await msg.finish()
    entry["claimed"] = True

    confirm_token = None
    held = False
    try:
        await msg.hold()
        held = True
        # 持有上下文期间 probe 可能已经超时；此时不再生成一个无人负责清理的 confirm。
        if _pending_probes.get(token) is not entry:
            await _release_sessions(msg)
            held = False
            return

        # confirm 口令至此才生成，因而每一次配对各持一枚，且只有本次的响应方知晓：
        # 发起方广播出去的那一枚 probe 口令不足以推出它，旁观者也就无从抢先应答。
        confirm_token = SecureRandom.randstr(HANDSHAKE_TOKEN_LENGTH)
        _pending_confirms[confirm_token] = {
            "probe_token": token,
            "initiator": initiator,
            "responder": msg,
            "initiator_bot_id": msg.session_info.sender_id,
        }
        await msg.send_message(Plain(f"{msg.session_info.prefixes[0]}bind channel confirm {confirm_token}"))
    except BaseException:
        entry["claimed"] = False
        if confirm_token:
            _pending_confirms.pop(confirm_token, None)
        if held:
            await _release_sessions(msg)
        raise


async def _close_handshake(msg: Bot.MessageSession, token: str) -> None:
    """
    闭合一轮握手。

    confirm 口令同样只能消费一次，且只在发起场景中生效：响应方发出的口令必然落在双方共处的
    那个场景里，出现在别处即说明它是被转贴过去的，据此可拒绝跨场景的冒认。

    :param token: 对方发出的 confirm 口令。
    """
    entry = _pending_confirms.get(token)
    if not entry:
        await msg.finish()
    if entry["initiator"].session_info.target_id != msg.session_info.target_id:
        await msg.finish()

    _pending_confirms.pop(token, None)
    _pending_probes.pop(entry["probe_token"], None)
    entry["responder_bot_id"] = msg.session_info.sender_id
    await _complete_channel_handshake(entry)


@b.command("auto {{I18N:core.help.bind.auto}}", required_admin=True, load=ENABLE_BIND_AUTO)
async def _(msg: Bot.MessageSession):
    await _start_handshake(msg)


@b.command("channel probe <token> {{I18N:core.help.bind.channel.internal}}", load=ENABLE_BIND_AUTO)
async def _(msg: Bot.MessageSession, token: str):
    await _respond_probe(msg, token)


@b.command("channel confirm <token> {{I18N:core.help.bind.channel.internal}}", load=ENABLE_BIND_AUTO)
async def _(msg: Bot.MessageSession, token: str):
    await _close_handshake(msg, token)


async def _complete_channel_handshake(entry: dict) -> None:
    """
    握手闭合后把两个场景合成同一条消息通道。

    此时已确认两个场景对应同一个现实场景，随后执行三项操作：合并场景组（数据共享）、
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
            initiator_target = initiator.session_info.target_union_info
            responder_target = responder.session_info.target_union_info

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
        await _release_sessions(initiator, responder)


async def _run_channel_handshake(entry: dict, initiator: Bot.MessageSession, responder: Bot.MessageSession) -> None:
    """
    合并场景组、统一通道号、互记机器人账号。调用方需持有 :data:`_handshake_lock`。
    """
    initiator_target = initiator.session_info.target_union_info
    responder_target = responder.session_info.target_union_info

    merged = initiator_target
    if initiator_target.union_id != responder_target.union_id:
        # 合并确认在发起侧进行：执行该命令的管理员位于发起侧。
        merged = await merge_target_unions(
            initiator, initiator_target, responder_target, "core.message.bind.auto.confirm.inherit"
        )
        if not merged:
            await initiator.send_message(I18NContext("core.message.bind.auto.cancelled"))
            return

    # 将对方所在的完整通道并入本场景通道。若只修改响应方这一行，它原通道中的第三个平台入口
    # 会被错误拆开；通道等价关系具有传递性，必须整体移动。
    channel_id = await TargetUnionInfo.unify_channels(
        initiator.session_info.target_id,
        responder.session_info.target_id,
    )
    if channel_id is None:
        await initiator.send_message(I18NContext("core.message.bind.auto.cancelled"))
        return

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
                "core.message.bind.auto.success",
                id=merged.union_id,
                channel=channel_id,
                disable_joke=True,
            )
        )


BackgroundTaskLifecycle.register_cleanup(
    "module:bind-handshake",
    cancel_bind_handshake_tasks,
    label="bind handshake background tasks",
)
