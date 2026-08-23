"""core.builtins.session 会话系统单元测试。"""

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

from core.builtins.session.context import ContextManager
from core.builtins.session.features import Features
from core.builtins.session.info import SessionInfo
from core.builtins.session.lock import ExecutionLockList
from core.builtins.session.tasks import SessionTaskManager
from core.database.models import SenderUnionInfo, TargetUnionBind, TargetUnionInfo
from core.tester import func_case, Tester
from core.tester.mock.session import MockMessageSession


async def _make_held_session(
    target_id: str,
    sender_id: str,
    client_name: str,
    *,
    reply_id: str | None = None,
):
    """建立不依赖真实平台 Queue 的等待结果会话。"""
    from core.builtins.session.internal import MessageSession

    class HeldSession(MessageSession):
        hold_calls = 0
        release_calls = 0

        async def hold(self):
            self.hold_calls += 1

        async def release(self):
            self.release_calls += 1

    return HeldSession(
        await SessionInfo.assign(
            target_id=target_id,
            target_from=f"{client_name}|Group",
            client_name=client_name,
            sender_id=sender_id,
            sender_from=client_name,
            reply_id=reply_id,
        )
    )


async def _test_features_inject_action_text():
    """测试 support_action_text 能注入会话

    inject_features() 以 asdict(features) 逐字段 setattr，SessionInfo 若缺少同名
    字段会在注入时抛错，故新增能力标志必须两处同步声明。
    """
    try:
        from core.builtins.session.info import SessionInfo

        session_info = await SessionInfo.assign(
            target_id="TEST|Group|action_text",
            target_from="TEST|Group",
            client_name="TEST",
            sender_id="TEST|1",
            features=Features(support_action_text=True),
        )
        return session_info.support_action_text is True
    except Exception:
        return False


async def _test_release_context_tolerates_prior_platform_cleanup():
    """平台关闭先清空 context 时，后台 release 仍应移除 hold 计数而不抛错。"""
    session_id = "session-release-after-platform-cleanup"
    session = SimpleNamespace(session_id=session_id)
    ContextManager.context[session_id] = object()
    ContextManager.context_marks_hold[session_id] = 1
    ContextManager.context.pop(session_id)
    try:
        ContextManager.release_context(session)
        return session_id not in ContextManager.context_marks_hold
    except KeyError:
        return False
    finally:
        ContextManager.context.pop(session_id, None)
        ContextManager.context_marks_hold.pop(session_id, None)


async def _test_features_inject_markdown_table():
    """测试 support_markdown_table 能注入并随会话序列化"""
    try:
        from core.builtins.session.info import SessionInfo

        session_info = await SessionInfo.assign(
            target_id="TEST|Group|markdown_table",
            target_from="TEST|Group",
            client_name="TEST",
            sender_id="TEST|1",
            features=Features(support_markdown_table=True),
        )
        return session_info.support_markdown_table is True
    except Exception:
        return False


async def _test_session_refresh_updates_derived_union_state():
    """跨进程入队后刷新会话时，权限与场景配置的派生字段必须一起更新。"""
    target_id = "TEST|Group|refresh-derived-state"
    sender_id = "TEST|refresh-derived-state"
    session_info = await SessionInfo.assign(
        target_id=target_id,
        target_from="TEST|Group",
        client_name="TEST",
        sender_id=sender_id,
        prefixes=["/"],
    )
    target = await TargetUnionInfo.get_by_target_id(target_id)
    sender = await SenderUnionInfo.get_by_sender_id(sender_id)
    target.locale = "en_us"
    target.muted = True
    target.modules = ["refresh-module"]
    target.banned_users = [sender.union_id]
    target.custom_admins = [sender.union_id]
    target.target_data = {
        **target.target_data,
        "command_prefix": ["!"],
        "timezone_offset": "+8",
        "invalid_module_prompt": False,
    }
    sender.superuser = True
    sender.petal = 42
    sender.sender_data = {**sender.sender_data, "typing_prompt": False}
    await target.save(update_fields=["locale", "muted", "modules", "banned_users", "custom_admins", "target_data"])
    await sender.save(update_fields=["superuser", "petal", "sender_data"])
    await TargetUnionBind.filter(target_id=target_id).update(channel_id=7)

    await session_info.refresh_info()
    return (
        session_info.superuser
        and session_info.petal == 42
        and session_info.banned_users == [sender.union_id]
        and session_info.custom_admins == [sender.union_id]
        and session_info.muted is True
        and session_info.locale.locale == "en_us"
        and session_info.platform_prefixes == ["/"]
        and session_info.prefixes[:2] == ["/", "!"]
        and session_info._tz_offset == "+8"
        and session_info.timezone_offset.total_seconds() == 8 * 3600
        and session_info.enabled_modules == ["refresh-module"]
        and session_info.target_channel_id == 7
        and not session_info.typing_prompt_enabled
        and not session_info.invalid_module_prompt_enabled
    )


async def _test_session_refresh_does_not_recreate_deleted_unions():
    """入队后的旧消息不能复活已被管理员删除的用户或场景 Union。"""
    sender_target_id = "TEST|Group|refresh-deleted-sender"
    sender_id = "TEST|refresh-deleted-sender"
    target_target_id = "TEST|Group|refresh-deleted-target"
    target_sender_id = "TEST|refresh-deleted-target"

    sender_session = await SessionInfo.assign(
        target_id=sender_target_id,
        target_from="TEST|Group",
        client_name="TEST",
        sender_id=sender_id,
    )
    target_session = await SessionInfo.assign(
        target_id=target_target_id,
        target_from="TEST|Group",
        client_name="TEST",
        sender_id=target_sender_id,
    )

    try:
        await sender_session.sender_union_info.delete_union()
        try:
            await sender_session.refresh_info()
        except ValueError as exc:
            sender_failed_closed = "SenderUnionInfo not found" in str(exc)
        else:
            sender_failed_closed = False

        await target_session.target_union_info.delete_union()
        try:
            await target_session.refresh_info()
        except ValueError as exc:
            target_failed_closed = "TargetUnionInfo not found" in str(exc)
        else:
            target_failed_closed = False

        return (
            sender_failed_closed
            and target_failed_closed
            and await SenderUnionInfo.get_by_sender_id(sender_id, create=False) is None
            and await TargetUnionInfo.get_by_target_id(target_target_id, create=False) is None
        )
    finally:
        for model, platform_id in (
            (SenderUnionInfo, sender_id),
            (TargetUnionInfo, sender_target_id),
            (SenderUnionInfo, target_sender_id),
            (TargetUnionInfo, target_target_id),
        ):
            union = await model.resolve_union(platform_id, create=False)
            if union:
                await union.delete_union()


def _test_features_override():
    """测试 Features.override()"""
    try:
        features = Features.override(support_image=True, support_voice=True)
        if features.support_image is not True:
            return False
        if features.support_voice is not True:
            return False
        if features.support_mention is not False:
            return False
        return True
    except Exception:
        return False


async def _test_lock_add_remove():
    """测试 ExecutionLockList 添加和移除"""
    try:
        msg = MockMessageSession("~test")
        await msg.async_init("~test")

        if ExecutionLockList.check(msg):
            return False

        ExecutionLockList.add(msg)
        if not ExecutionLockList.check(msg):
            return False

        ExecutionLockList.remove(msg)
        if ExecutionLockList.check(msg):
            return False

        return True
    except Exception:
        return False


async def _test_lock_multiple_users():
    """测试多个用户的锁"""
    try:
        msg1 = MockMessageSession("~test")
        await msg1.async_init("~test")

        msg2 = MockMessageSession("~test")
        msg2.session_info = await msg1.session_info.__class__.assign(
            target_id="TEST|Console|0",
            client_name="TEST",
            target_from="TEST",
            sender_id="TEST|1",
            sender_from="TEST",
            sender_name="TEST2",
        )

        ExecutionLockList.add(msg1)
        ExecutionLockList.add(msg2)

        if not ExecutionLockList.check(msg1):
            return False
        if not ExecutionLockList.check(msg2):
            return False

        ExecutionLockList.remove(msg1)
        if ExecutionLockList.check(msg1):
            return False
        if not ExecutionLockList.check(msg2):
            return False

        ExecutionLockList.remove(msg2)

        return True
    except Exception:
        return False


async def _test_lock_shared_by_bound_identities():
    """同一用户 Union 下的不同平台身份应共享执行锁。"""
    try:
        first = MockMessageSession("~test")
        await first.async_init("~test")
        await first.session_info.sender_union_info.bind_id("TEST|bound-lock")

        second = MockMessageSession("~test")
        second.session_info = await first.session_info.__class__.assign(
            target_id="TEST|Console|0",
            client_name="TEST",
            target_from="TEST",
            sender_id="TEST|bound-lock",
            sender_from="TEST",
            sender_name="TEST2",
        )

        ExecutionLockList.add(first)
        locked = ExecutionLockList.check(second)
        ExecutionLockList.remove(first)
        return locked and not ExecutionLockList.check(second)
    except Exception:
        ExecutionLockList._list.clear()
        return False


async def _test_lock_non_owner_cannot_release():
    """同一 Union 中未取得锁的会话不能释放所有者的锁。"""
    owner = MockMessageSession("~test")
    await owner.async_init("~test")
    await owner.session_info.sender_union_info.bind_id("TEST|lock-contender")

    contender = MockMessageSession("~test")
    contender.session_info = await owner.session_info.__class__.assign(
        target_id="TEST|Console|0",
        client_name="TEST",
        target_from="TEST",
        sender_id="TEST|lock-contender",
        sender_from="TEST",
        sender_name="TEST2",
    )

    ExecutionLockList._list.clear()
    try:
        ExecutionLockList.add(owner)
        ExecutionLockList.remove(contender)
        return ExecutionLockList.check(owner) and ExecutionLockList.check(contender)
    finally:
        ExecutionLockList.remove(owner)
        ExecutionLockList._list.clear()


async def _test_old_owner_cannot_release_reacquired_lock():
    """会话提前释放后，其最终清理不能删除另一会话后来取得的同一把锁。"""
    first = MockMessageSession("~test")
    await first.async_init("~test")
    await first.session_info.sender_union_info.bind_id("TEST|lock-reacquired")

    second = MockMessageSession("~test")
    second.session_info = await first.session_info.__class__.assign(
        target_id="TEST|Console|0",
        client_name="TEST",
        target_from="TEST",
        sender_id="TEST|lock-reacquired",
        sender_from="TEST",
        sender_name="TEST2",
    )

    ExecutionLockList._list.clear()
    try:
        ExecutionLockList.add(first)
        ExecutionLockList.remove(first)
        ExecutionLockList.add(second)
        ExecutionLockList.remove(first)
        return ExecutionLockList.check(second)
    finally:
        ExecutionLockList.remove(second)
        ExecutionLockList._list.clear()


async def _test_lock_get():
    """测试 ExecutionLockList.get()"""
    try:
        msg = MockMessageSession("~test")
        await msg.async_init("~test")

        ExecutionLockList.add(msg)
        lock_set = ExecutionLockList.get()
        if not isinstance(lock_set, set):
            return False
        if msg.session_info.sender_union_id not in lock_set:
            return False

        ExecutionLockList.remove(msg)

        return True
    except Exception:
        return False


async def _test_lock_detects_union_merge_by_physical_bindings():
    """Union 合并会更换 Union ID，但不得让新组中的另一账号绕过旧 lease。"""
    from core.builtins.session.internal import MessageSession

    first_sender = "TEST|lock-merge-first"
    second_sender = "TEST|lock-merge-second"
    target_id = "TEST|Group|lock-merge"
    first_info = await SessionInfo.assign(
        target_id=target_id,
        target_from="TEST|Group",
        client_name="TEST",
        sender_id=first_sender,
        sender_from="TEST",
    )
    second_info = await SessionInfo.assign(
        target_id=target_id,
        target_from="TEST|Group",
        client_name="TEST",
        sender_id=second_sender,
        sender_from="TEST",
    )
    owner = MessageSession(first_info)
    contender = MessageSession(second_info)
    ExecutionLockList._list.clear()
    merged = None
    try:
        if not await ExecutionLockList.acquire(owner):
            return False
        merged = await first_info.sender_union_info.merge_union(second_info.sender_union_info)
        if merged is None:
            return False
        await contender.session_info.refresh_info()
        return await ExecutionLockList.is_locked(contender) and not await ExecutionLockList.acquire(contender)
    finally:
        ExecutionLockList.remove(owner)
        ExecutionLockList.remove(contender)
        ExecutionLockList._list.clear()
        if merged:
            await merged.delete_union()
        target = await TargetUnionInfo.get_by_target_id(target_id, create=False)
        if target:
            await target.delete_union()


async def _test_wait_resume_reacquires_after_competing_command():
    """等待结果到达时，原 continuation 必须等待期间启动的新命令释放锁。"""
    from core.builtins.session.internal import MessageSession

    class WaitSession(MessageSession):
        async def end_typing(self):
            return None

        async def hold(self):
            return None

        async def release(self):
            return None

    session_info = await SessionInfo.assign(
        target_id="TEST|Group|wait-reacquire",
        target_from="TEST|Group",
        client_name="TEST",
        sender_id="TEST|wait-reacquire",
        sender_from="TEST",
    )
    owner = WaitSession(session_info)
    contender = MessageSession(
        await SessionInfo.assign(
            target_id=session_info.target_id,
            target_from=session_info.target_from,
            client_name=session_info.client_name,
            sender_id=session_info.sender_id,
            sender_from=session_info.sender_from,
        )
    )
    incoming = WaitSession(
        await SessionInfo.assign(
            target_id=session_info.target_id,
            target_from=session_info.target_from,
            client_name=session_info.client_name,
            sender_id=session_info.sender_id,
            sender_from=session_info.sender_from,
        )
    )
    SessionTaskManager._task_list.clear()
    ExecutionLockList._list.clear()
    wait_task = None
    try:
        if not await ExecutionLockList.acquire(owner):
            return False
        wait_task = asyncio.create_task(owner.wait_next_message(timeout=1))
        for _ in range(20):
            if SessionTaskManager.get() and not ExecutionLockList.check(owner):
                break
            await asyncio.sleep(0)
        else:
            return False

        if not await ExecutionLockList.acquire(contender):
            return False
        if not await SessionTaskManager.check(incoming):
            return False
        await asyncio.sleep(0)
        if wait_task.done():
            return False

        ExecutionLockList.remove(contender)
        result = await asyncio.wait_for(wait_task, timeout=0.5)
        return result is incoming and ExecutionLockList.check(owner) and not SessionTaskManager.get()
    finally:
        if wait_task and not wait_task.done():
            wait_task.cancel()
            try:
                await wait_task
            except asyncio.CancelledError:
                pass
        ExecutionLockList.remove(owner)
        ExecutionLockList.remove(contender)
        ExecutionLockList._list.clear()
        SessionTaskManager._task_list.clear()


async def _test_cancelled_wait_leaves_no_task_or_lease():
    """取消已释放执行锁的等待时，不得遗留 waiter 或重获 lease。"""
    from core.builtins.session.internal import MessageSession

    class WaitSession(MessageSession):
        async def end_typing(self):
            return None

    msg = WaitSession(
        await SessionInfo.assign(
            target_id="TEST|Group|wait-cancel-cleanup",
            target_from="TEST|Group",
            client_name="TEST",
            sender_id="TEST|wait-cancel-cleanup",
            sender_from="TEST",
        )
    )
    SessionTaskManager._task_list.clear()
    ExecutionLockList._list.clear()
    task = None
    try:
        if not await ExecutionLockList.acquire(msg):
            return False
        task = asyncio.create_task(msg.wait_next_message(timeout=None))
        for _ in range(20):
            if SessionTaskManager.get() and not ExecutionLockList.check(msg):
                break
            await asyncio.sleep(0)
        else:
            return False
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return not SessionTaskManager.get() and not ExecutionLockList.get()
    finally:
        if task and not task.done():
            task.cancel()
        ExecutionLockList.remove(msg)
        ExecutionLockList._list.clear()
        SessionTaskManager._task_list.clear()


async def _test_execution_lock_state_does_not_survive_session_serialization():
    """SessionInfo 跨进程复制不能携带或释放原 MessageSession 的 lease。"""
    from core.builtins.converter import converter
    from core.builtins.session.internal import MessageSession

    owner = MessageSession(
        await SessionInfo.assign(
            target_id="TEST|Group|lock-serialization",
            target_from="TEST|Group",
            client_name="TEST",
            sender_id="TEST|lock-serialization",
            sender_from="TEST",
        )
    )
    ExecutionLockList._list.clear()
    ExecutionLockList._reservations.clear()
    try:
        if not await ExecutionLockList.acquire(owner):
            return False
        copied_info = converter.structure(converter.unstructure(owner.session_info), SessionInfo)
        copied = MessageSession(copied_info)
        copied_removed = ExecutionLockList.remove(copied)
        return (
            not copied_removed
            and ExecutionLockList.check(owner)
            and ExecutionLockList.state(owner).lock_token is not None
            and ExecutionLockList.state(copied).lock_token is None
        )
    finally:
        ExecutionLockList.remove(owner)
        ExecutionLockList._list.clear()
        ExecutionLockList._reservations.clear()


async def _test_execution_lock_count_counts_leases():
    """多绑定账号只算一条命令，exclude 只排除当前执行域。"""
    from core.builtins.session.internal import MessageSession

    owner = MessageSession(
        await SessionInfo.assign(
            target_id="TEST|Group|lock-count",
            target_from="TEST|Group",
            client_name="TEST",
            sender_id="TEST|lock-count-owner",
            sender_from="TEST",
        )
    )
    await owner.session_info.sender_union_info.bind_id("TEST|lock-count-bound")
    other = MessageSession(
        await SessionInfo.assign(
            target_id="TEST|Group|lock-count",
            target_from="TEST|Group",
            client_name="TEST",
            sender_id="TEST|lock-count-other",
            sender_from="TEST",
        )
    )
    ExecutionLockList._list.clear()
    ExecutionLockList._reservations.clear()
    try:
        if not await ExecutionLockList.acquire(owner):
            return False
        owner_count_ok = ExecutionLockList.count() == 1 and ExecutionLockList.count(exclude=owner) == 0
        if not await ExecutionLockList.acquire(other):
            return False
        return owner_count_ok and ExecutionLockList.count() == 2 and ExecutionLockList.count(exclude=owner) == 1
    finally:
        ExecutionLockList.remove(owner)
        ExecutionLockList.remove(other)
        ExecutionLockList._list.clear()
        ExecutionLockList._reservations.clear()


async def _test_partial_overlap_merge_reservations_do_not_deadlock():
    """A+B 与 C+B 这类部分重叠 reservation 中，后进入者应主动让出。"""
    from core.builtins.session.internal import MessageSession

    first = MessageSession(
        await SessionInfo.assign(
            target_id="TEST|Group|partial-reservation",
            target_from="TEST|Group",
            client_name="TEST",
            sender_id="TEST|partial-reservation-a",
            sender_from="TEST",
        )
    )
    second = MessageSession(
        await SessionInfo.assign(
            target_id="TEST|Group|partial-reservation",
            target_from="TEST|Group",
            client_name="TEST",
            sender_id="TEST|partial-reservation-c",
            sender_from="TEST",
        )
    )
    ExecutionLockList._list.clear()
    ExecutionLockList._reservations.clear()
    try:
        if not await ExecutionLockList.acquire(first) or not await ExecutionLockList.acquire(second):
            return False
        if not await ExecutionLockList.reserve(first, {"TEST|shared-reservation"}):
            return False
        second_reserved = await asyncio.wait_for(
            ExecutionLockList.reserve(second, {"TEST|shared-reservation"}),
            timeout=0.2,
        )
        first_token = ExecutionLockList.state(first).lock_token
        return (
            not second_reserved
            and first_token in ExecutionLockList._reservations
            and ExecutionLockList.check(first)
            and ExecutionLockList.state(second).lock_token is None
            and ExecutionLockList.count() == 1
        )
    finally:
        ExecutionLockList.remove(first)
        ExecutionLockList.remove(second)
        ExecutionLockList._list.clear()
        ExecutionLockList._reservations.clear()


async def _test_active_sender_leases_are_barriered_before_merge():
    """两个活跃 Union 合并前须等待另一 lease，期间阻止双方新命令进入。"""
    from core.builtins.session.internal import MessageSession
    from core.union_merge import apply_sender_merge, plan_sender_merge, reserve_sender_merge

    target_id = "TEST|Group|active-sender-merge-barrier"
    first_id = "TEST|active-sender-merge-first"
    second_id = "TEST|active-sender-merge-second"
    first = MessageSession(
        await SessionInfo.assign(
            target_id=target_id,
            target_from="TEST|Group",
            client_name="TEST",
            sender_id=first_id,
            sender_from="TEST",
        )
    )
    merge_command = MessageSession(
        await SessionInfo.assign(
            target_id=target_id,
            target_from="TEST|Group",
            client_name="TEST",
            sender_id=second_id,
            sender_from="TEST",
        )
    )
    first_contender = MessageSession(
        await SessionInfo.assign(
            target_id=target_id,
            target_from="TEST|Group",
            client_name="TEST",
            sender_id=first_id,
            sender_from="TEST",
        )
    )
    ExecutionLockList._list.clear()
    ExecutionLockList._reservations.clear()
    reserve_task = None
    merged = None
    try:
        if not await ExecutionLockList.acquire(first) or not await ExecutionLockList.acquire(merge_command):
            return False
        plan = await plan_sender_merge(
            first.session_info.sender_union_info, merge_command.session_info.sender_union_info
        )
        reserve_task = asyncio.create_task(reserve_sender_merge(merge_command, plan))
        for _ in range(20):
            if ExecutionLockList._reservations:
                break
            await asyncio.sleep(0)
        else:
            return False
        if reserve_task.done() or await ExecutionLockList.acquire(first_contender):
            return False

        ExecutionLockList.remove(first)
        reserved_plan = await asyncio.wait_for(reserve_task, timeout=0.5)
        with patch("core.union_merge.write_merge_log"):
            merged = await apply_sender_merge(reserved_plan, set(), merge_command)
        keys = ExecutionLockList.get()
        return (
            merged is not None
            and first_id in keys
            and second_id in keys
            and merged.union_id in keys
            and ExecutionLockList.count() == 1
            and not ExecutionLockList._reservations
        )
    finally:
        if reserve_task and not reserve_task.done():
            reserve_task.cancel()
            try:
                await reserve_task
            except asyncio.CancelledError:
                pass
        ExecutionLockList.remove(first)
        ExecutionLockList.remove(merge_command)
        ExecutionLockList.remove(first_contender)
        ExecutionLockList._list.clear()
        ExecutionLockList._reservations.clear()
        if merged:
            await merged.delete_union()
        target = await TargetUnionInfo.get_by_target_id(target_id, create=False)
        if target:
            await target.delete_union()


async def _test_cross_user_wait_result_keeps_root_lock_subject():
    """wait_anyone 的回复者会话继续 sleep 时，lease 仍须覆盖命令发起者。"""
    from core.builtins.session.internal import MessageSession

    class LifecycleSession(MessageSession):
        hold_calls = 0
        release_calls = 0

        async def end_typing(self):
            return None

        async def hold(self):
            self.hold_calls += 1

        async def release(self):
            self.release_calls += 1

    target_id = "TEST|Group|cross-user-wait-subject"
    owner = LifecycleSession(
        await SessionInfo.assign(
            target_id=target_id,
            target_from="TEST|Group",
            client_name="TEST",
            sender_id="TEST|cross-user-owner",
            sender_from="TEST",
        )
    )
    incoming = LifecycleSession(
        await SessionInfo.assign(
            target_id=target_id,
            target_from="TEST|Group",
            client_name="TEST",
            sender_id="TEST|cross-user-responder",
            sender_from="TEST",
        )
    )
    owner_contender = MessageSession(
        await SessionInfo.assign(
            target_id=target_id,
            target_from="TEST|Group",
            client_name="TEST",
            sender_id=owner.session_info.sender_id,
            sender_from="TEST",
        )
    )
    responder_contender = MessageSession(
        await SessionInfo.assign(
            target_id=target_id,
            target_from="TEST|Group",
            client_name="TEST",
            sender_id=incoming.session_info.sender_id,
            sender_from="TEST",
        )
    )
    SessionTaskManager._task_list.clear()
    ExecutionLockList._list.clear()
    ExecutionLockList._reservations.clear()
    wait_task = None
    try:
        if not await ExecutionLockList.acquire(owner):
            return False
        wait_task = asyncio.create_task(owner.wait_anyone(timeout=1))
        for _ in range(20):
            if SessionTaskManager.get() and not ExecutionLockList.check(owner):
                break
            await asyncio.sleep(0)
        else:
            return False

        if not await SessionTaskManager.check(incoming):
            return False
        result = await asyncio.wait_for(wait_task, timeout=0.5)
        await result.sleep(0)
        keys = ExecutionLockList.get()
        owner_is_serialized = not await ExecutionLockList.acquire(owner_contender)
        responder_is_free = await ExecutionLockList.acquire(responder_contender)
        await owner.release_execution_resources()
        return (
            result is incoming
            and owner.session_info.sender_id in keys
            and incoming.session_info.sender_id not in keys
            and owner_is_serialized
            and responder_is_free
            and incoming.hold_calls == 1
            and incoming.release_calls == 1
        )
    finally:
        if wait_task and not wait_task.done():
            wait_task.cancel()
            try:
                await wait_task
            except asyncio.CancelledError:
                pass
        ExecutionLockList.remove(owner)
        ExecutionLockList.remove(owner_contender)
        ExecutionLockList.remove(responder_contender)
        ExecutionLockList._list.clear()
        ExecutionLockList._reservations.clear()
        SessionTaskManager._task_list.clear()


async def _test_wait_result_context_release_retries_once():
    """wait-result context 第一次释放失败时应只重试失败项。"""
    from core.builtins.session.internal import MessageSession

    class RetryReleaseSession(MessageSession):
        release_calls = 0

        async def release(self):
            self.release_calls += 1
            if self.release_calls == 1:
                raise RuntimeError("transient release failure")

    class SuccessfulReleaseSession(MessageSession):
        release_calls = 0

        async def release(self):
            self.release_calls += 1

    root = MessageSession(
        await SessionInfo.assign(
            target_id="TEST|Group|context-release-retry",
            target_from="TEST|Group",
            client_name="TEST",
            sender_id="TEST|context-release-retry",
            sender_from="TEST",
        )
    )
    retrying = RetryReleaseSession(root.session_info)
    successful = SuccessfulReleaseSession(root.session_info)
    root._adopt_wait_result(retrying)
    root._adopt_wait_result(successful)
    await root.release_execution_resources()
    return (
        retrying.release_calls == 2
        and successful.release_calls == 1
        and not ExecutionLockList.state(root).held_contexts
    )


async def _test_wait_confirm_can_preserve_merge_barrier():
    """Union 冲突选择等待回复时可以保持已建立的 execution barrier。"""
    from core.builtins.message.chain import MessageChain
    from core.builtins.session.internal import MessageSession

    class IncomingSession(MessageSession):
        hold_calls = 0
        release_calls = 0

        async def hold(self):
            self.hold_calls += 1

        async def release(self):
            self.release_calls += 1

    incoming = IncomingSession(
        await SessionInfo.assign(
            target_id="TEST|Group|preserve-merge-barrier",
            target_from="TEST|Group",
            client_name="TEST",
            sender_id="TEST|preserve-merge-barrier",
            sender_from="TEST",
            messages=MessageChain.assign("是"),
        )
    )

    class PromptSession(MessageSession):
        lock_seen_during_send = False

        async def send_message(self, *args, **kwargs):
            self.lock_seen_during_send = ExecutionLockList.check(self)
            await SessionTaskManager.check(incoming)
            return type("Sent", (), {"message_id": ["prompt"]})()

        async def end_typing(self):
            return None

    owner = PromptSession(
        await SessionInfo.assign(
            target_id=incoming.session_info.target_id,
            target_from=incoming.session_info.target_from,
            client_name=incoming.session_info.client_name,
            sender_id=incoming.session_info.sender_id,
            sender_from=incoming.session_info.sender_from,
        )
    )
    SessionTaskManager._task_list.clear()
    ExecutionLockList._list.clear()
    ExecutionLockList._reservations.clear()
    try:
        if not await ExecutionLockList.acquire(owner):
            return False
        confirmed = await owner.wait_confirm(
            "prompt",
            delete=False,
            timeout=0.5,
            release_execution_lock=False,
        )
        lock_still_owned = ExecutionLockList.check(owner)
        await owner.release_execution_resources()
        return (
            confirmed
            and owner.lock_seen_during_send
            and lock_still_owned
            and incoming.hold_calls == 1
            and incoming.release_calls == 1
        )
    finally:
        ExecutionLockList.remove(owner)
        ExecutionLockList._list.clear()
        ExecutionLockList._reservations.clear()
        SessionTaskManager._task_list.clear()


async def _test_parser_wait_result_keeps_root_merge_barrier():
    """真实 parser 消费等待回复后不得释放根命令持有的 merge barrier。"""
    from core.builtins.message.chain import MessageChain
    from core.builtins.parser.message import parser
    from core.builtins.session.internal import MessageSession

    class IncomingSession(MessageSession):
        hold_calls = 0
        release_calls = 0

        async def hold(self):
            self.hold_calls += 1

        async def release(self):
            self.release_calls += 1

    target_id = "TEST|Group|parser-preserve-merge-barrier"
    sender_id = "TEST|parser-preserve-merge-barrier"
    owner = MessageSession(
        await SessionInfo.assign(
            target_id=target_id,
            target_from="TEST|Group",
            client_name="TEST",
            sender_id=sender_id,
            sender_from="TEST",
        )
    )
    incoming = IncomingSession(
        await SessionInfo.assign(
            target_id=target_id,
            target_from="TEST|Group",
            client_name="TEST",
            sender_id=sender_id,
            sender_from="TEST",
            messages=MessageChain.assign("是"),
        )
    )
    flag = asyncio.Event()
    SessionTaskManager._task_list.clear()
    ExecutionLockList._list.clear()
    ExecutionLockList._reservations.clear()
    try:
        if not await ExecutionLockList.acquire(owner):
            return False
        if not await ExecutionLockList.reserve(owner, {"TEST|merge-peer"}):
            return False
        token = ExecutionLockList.state(owner).lock_token
        SessionTaskManager.add_task(owner, flag, timeout=60)

        await parser(incoming)

        result = SessionTaskManager.get_result(owner)
        lease_intact = (
            token is not None
            and ExecutionLockList.state(owner).lock_token == token
            and token in ExecutionLockList._list
            and token in ExecutionLockList._reservations
        )
        await owner.release_execution_resources()
        return (
            flag.is_set()
            and result is incoming
            and incoming._execution_state is owner._execution_state
            and not incoming._execution_state_owner
            and lease_intact
            and incoming.hold_calls == 1
            and incoming.release_calls == 1
        )
    finally:
        SessionTaskManager.remove_task(owner)
        ExecutionLockList.remove(owner)
        ExecutionLockList._list.clear()
        ExecutionLockList._reservations.clear()
        SessionTaskManager._task_list.clear()


async def _test_inactive_wait_releases_context_acquired_during_hold():
    """hold 跨进程期间 waiter 被移除时，不得发布结果或遗留 context。"""
    from core.builtins.session.internal import MessageSession

    class BlockingHoldSession(MessageSession):
        hold_started = asyncio.Event()
        allow_hold = asyncio.Event()
        release_calls = 0

        async def hold(self):
            self.hold_started.set()
            await self.allow_hold.wait()

        async def release(self):
            self.release_calls += 1

    waiting = MessageSession(
        await SessionInfo.assign(
            target_id="TEST|Group|inactive-hold",
            target_from="TEST|Group",
            client_name="TEST",
            sender_id="TEST|inactive-hold",
            sender_from="TEST",
        )
    )
    incoming = BlockingHoldSession(waiting.session_info)
    flag = asyncio.Event()
    SessionTaskManager._task_list.clear()
    SessionTaskManager.add_task(waiting, flag, timeout=60)
    check_task = asyncio.create_task(SessionTaskManager.check(incoming))
    try:
        await asyncio.wait_for(incoming.hold_started.wait(), timeout=0.5)
        task_info = SessionTaskManager.remove_task(waiting)
        incoming.allow_hold.set()
        handled = await asyncio.wait_for(check_task, timeout=0.5)
        return (
            not handled
            and task_info is not None
            and "result" not in task_info
            and incoming.release_calls == 1
            and not flag.is_set()
        )
    finally:
        if not check_task.done():
            check_task.cancel()
        SessionTaskManager._task_list.clear()


async def _test_sleep_waits_for_competing_lease_before_resuming():
    """sleep 返回后的 continuation 必须等竞争命令释放后再重获 lease。"""
    from core.builtins.session.internal import MessageSession

    original_sleep = asyncio.sleep
    sleep_entered = asyncio.Event()
    finish_sleep = asyncio.Event()

    async def controlled_sleep(_seconds):
        sleep_entered.set()
        await finish_sleep.wait()

    session_info = await SessionInfo.assign(
        target_id="TEST|Group|sleep-reacquire",
        target_from="TEST|Group",
        client_name="TEST",
        sender_id="TEST|sleep-reacquire",
        sender_from="TEST",
    )
    owner = MessageSession(session_info)
    contender = MessageSession(
        await SessionInfo.assign(
            target_id=session_info.target_id,
            target_from=session_info.target_from,
            client_name=session_info.client_name,
            sender_id=session_info.sender_id,
            sender_from=session_info.sender_from,
        )
    )
    ExecutionLockList._list.clear()
    ExecutionLockList._reservations.clear()
    sleep_task = None
    try:
        if not await ExecutionLockList.acquire(owner):
            return False
        with patch("core.builtins.session.internal.asyncio.sleep", controlled_sleep):
            sleep_task = asyncio.create_task(owner.sleep(10))
            await sleep_entered.wait()
            if not await ExecutionLockList.acquire(contender):
                return False
            finish_sleep.set()
            await original_sleep(0)
            if sleep_task.done():
                return False
            ExecutionLockList.remove(contender)
            await asyncio.wait_for(sleep_task, timeout=0.5)
        return ExecutionLockList.check(owner)
    finally:
        if sleep_task and not sleep_task.done():
            sleep_task.cancel()
        ExecutionLockList.remove(owner)
        ExecutionLockList.remove(contender)
        ExecutionLockList._list.clear()
        ExecutionLockList._reservations.clear()


async def _test_cancelled_sleep_reacquire_keeps_competing_lease():
    """continuation 等待重获时被取消，不得破坏竞争者 lease 或留下幽灵锁。"""
    from core.builtins.session.internal import MessageSession

    original_sleep = asyncio.sleep
    sleep_entered = asyncio.Event()
    finish_sleep = asyncio.Event()

    async def controlled_sleep(_seconds):
        sleep_entered.set()
        await finish_sleep.wait()

    session_info = await SessionInfo.assign(
        target_id="TEST|Group|sleep-cancel-reacquire",
        target_from="TEST|Group",
        client_name="TEST",
        sender_id="TEST|sleep-cancel-reacquire",
        sender_from="TEST",
    )
    owner = MessageSession(session_info)
    contender = MessageSession(
        await SessionInfo.assign(
            target_id=session_info.target_id,
            target_from=session_info.target_from,
            client_name=session_info.client_name,
            sender_id=session_info.sender_id,
            sender_from=session_info.sender_from,
        )
    )
    ExecutionLockList._list.clear()
    ExecutionLockList._reservations.clear()
    sleep_task = None
    try:
        if not await ExecutionLockList.acquire(owner):
            return False
        with patch("core.builtins.session.internal.asyncio.sleep", controlled_sleep):
            sleep_task = asyncio.create_task(owner.sleep(10))
            await sleep_entered.wait()
            if not await ExecutionLockList.acquire(contender):
                return False
            finish_sleep.set()
            await original_sleep(0)
            if sleep_task.done():
                return False
            sleep_task.cancel()
            try:
                await sleep_task
            except asyncio.CancelledError:
                pass
        return ExecutionLockList.check(contender) and ExecutionLockList.count() == 1
    finally:
        if sleep_task and not sleep_task.done():
            sleep_task.cancel()
        ExecutionLockList.remove(owner)
        ExecutionLockList.remove(contender)
        ExecutionLockList._list.clear()
        ExecutionLockList._reservations.clear()


async def _test_task_add_and_get():
    """测试 SessionTaskManager 添加和获取任务"""
    try:
        SessionTaskManager._task_list.clear()

        msg = MockMessageSession("~test")
        await msg.async_init("~test")

        flag = asyncio.Event()
        SessionTaskManager.add_task(msg, flag, timeout=60)

        task_list = SessionTaskManager.get()
        session_info = msg.session_info

        # 任务用不可变的物理场景／账号 ID 建稳定 bucket；check() 再按当前
        # Union／channel 拓扑展开可命中的 bucket。
        if session_info.target_id not in task_list:
            return False
        if session_info.sender_id not in task_list[session_info.target_id]:
            return False
        if session_info.channel_key in task_list or session_info.target_union_id in task_list:
            return False

        SessionTaskManager._task_list.clear()

        return True
    except Exception:
        return False


async def _test_task_add_callback():
    """测试 SessionTaskManager 添加回调"""
    try:

        async def test_callback(session):
            pass

        msg = MockMessageSession("1")
        await msg.async_init("1")
        callback_key = SessionTaskManager.add_callback(msg, "12345", test_callback)
        callback_info = SessionTaskManager._callback_list.get(callback_key)
        if (
            callback_info is None
            or callback_info["primary_ids"] != ("12345",)
            or callback_info["timeout"] != 1800
            or callback_info["once"]
        ):
            return False

        del SessionTaskManager._callback_list[callback_key]

        return True
    except Exception:
        return False


async def _test_send_message_binds_button_callback_reply_id():
    """带 callback 的按钮应自动取得虚拟 reply_id，并与真实消息 ID 一起注册。"""
    from core.builtins.message.chain import MessageChain
    from core.builtins.message.elements import ButtonFrameElement
    from core.builtins.message.internal import Button
    from core.builtins.session.info import SessionInfo
    from core.builtins.session.internal import MessageSession
    from core.exports import exports
    from core.i18n import Locale

    captured = {}

    class FakeJobQueueServer:
        @classmethod
        async def client_send_message(cls, session_info, chain, **kwargs):
            captured["chain"] = chain
            return {"message_id": ["physical-message"]}

    async def callback(_session):
        pass

    session = SessionInfo(
        target_id="TEST|Group|callback",
        target_from="TEST|Group",
        client_name="TEST",
        sender_id="TEST|1",
        bot_id="bot-fallback",
        locale=Locale("zh_cn"),
        support_button=True,
        tmp={},
    )
    msg = MessageSession(session)
    SessionTaskManager._callback_list.clear()
    try:
        with patch.dict(exports, {"JobQueueServer": FakeJobQueueServer}):
            finished = await msg.send_message(
                MessageChain.assign(Button("Choose", "1")),
                callback=callback,
                callback_timeout=60,
                callback_once=True,
            )

        sendable = captured["chain"].as_sendable(session)
        frame = next(element for element in sendable if isinstance(element, ButtonFrameElement))
        virtual_reply_id = frame.rows[0].buttons[0].reply_id
        registered = list(SessionTaskManager._callback_list.values())
        return (
            finished.message_id == ["physical-message"]
            and virtual_reply_id is not None
            and len(registered) == 1
            and registered[0]["primary_ids"] == ("physical-message", virtual_reply_id)
            and registered[0]["fallback_ids"] == frozenset({"bot-fallback"})
            and registered[0]["timeout"] == 60
            and registered[0]["once"]
        )
    finally:
        SessionTaskManager._callback_list.clear()


async def _test_button_callback_registered_before_send_returns():
    """平台消息已显示但跨进程发送结果未回包时，立即点击按钮也不能丢 callback。"""
    from core.builtins.message.chain import MessageChain
    from core.builtins.message.elements import ButtonFrameElement
    from core.builtins.message.internal import Button
    from core.builtins.session.info import SessionInfo
    from core.builtins.session.internal import MessageSession
    from core.exports import exports
    from core.i18n import Locale

    called = 0

    async def callback(_session):
        nonlocal called
        called += 1

    session = SessionInfo(
        target_id="TEST|Group|callback-race",
        target_from="TEST|Group",
        client_name="TEST",
        sender_id="TEST|callback-race",
        bot_id="bot-fallback",
        locale=Locale("zh_cn"),
        support_button=True,
        tmp={},
    )
    msg = MessageSession(session)

    class RacingJobQueueServer:
        @classmethod
        async def client_send_message(cls, session_info, chain, **kwargs):
            sendable = chain.as_sendable(session_info)
            frame = next(element for element in sendable if isinstance(element, ButtonFrameElement))
            reply = MessageSession(
                SessionInfo(
                    target_id=session_info.target_id,
                    target_from=session_info.target_from,
                    client_name=session_info.client_name,
                    sender_id=session_info.sender_id,
                    reply_id=frame.rows[0].buttons[0].reply_id,
                    locale=session_info.locale,
                    tmp={},
                )
            )
            if not await SessionTaskManager.check(reply):
                raise RuntimeError("callback was not registered before platform send returned")
            return {"message_id": ["physical-message"]}

    SessionTaskManager._callback_list.clear()
    try:
        with patch.dict(exports, {"JobQueueServer": RacingJobQueueServer}):
            finished = await msg.send_message(MessageChain.assign(Button("Choose", "1")), callback=callback)
        registered = list(SessionTaskManager._callback_list.values())
        return (
            called == 1
            and finished.message_id == ["physical-message"]
            and len(registered) == 1
            and "physical-message" in registered[0]["primary_ids"]
        )
    finally:
        SessionTaskManager._callback_list.clear()


async def _test_send_failure_does_not_leave_callback():
    """平台以空消息 ID 表示发送失败时不能留下虚拟 ID 或 bot_id callback。"""
    from core.builtins.message.chain import MessageChain
    from core.builtins.message.internal import Button
    from core.builtins.session.info import SessionInfo
    from core.builtins.session.internal import MessageSession
    from core.exports import exports
    from core.i18n import Locale

    class FailedJobQueueServer:
        @classmethod
        async def client_send_message(cls, session_info, chain, **kwargs):
            return {"message_id": []}

    async def callback(_session):
        return None

    msg = MessageSession(
        SessionInfo(
            target_id="TEST|Group|callback-failed-send",
            target_from="TEST|Group",
            client_name="TEST",
            sender_id="TEST|callback-failed-send",
            bot_id="bot-fallback",
            locale=Locale("zh_cn"),
            support_button=True,
            tmp={},
        )
    )
    SessionTaskManager._callback_list.clear()
    try:
        with patch.dict(exports, {"JobQueueServer": FailedJobQueueServer}):
            finished = await msg.send_message(MessageChain.assign(Button("Choose", "1")), callback=callback)
        return finished.message_id == [] and not SessionTaskManager._callback_list
    finally:
        SessionTaskManager._callback_list.clear()


async def _test_virtual_reply_id_triggers_callback():
    """按钮交互写入虚拟 reply_id 后应复用普通 callback 匹配。"""
    SessionTaskManager._callback_list.clear()
    called = False

    async def callback(_session):
        nonlocal called
        called = True

    msg = MockMessageSession("1")
    await msg.async_init("1")
    msg.session_info.reply_id = "virtual-reply"
    SessionTaskManager.add_callback(msg, "virtual-reply", callback)
    handled = await SessionTaskManager.check(msg)
    SessionTaskManager._callback_list.clear()
    return called and handled


async def _test_callback_remains_active_across_aliases():
    """同一 callback 的真实／虚拟回复别名在有效期内均可重复命中。"""
    SessionTaskManager._callback_list.clear()
    called = 0

    async def callback(_session):
        nonlocal called
        called += 1

    first = MockMessageSession("1")
    await first.async_init("1")
    first.session_info.reply_id = "physical-reply"

    second = MockMessageSession("1")
    await second.async_init("1")
    second.session_info.reply_id = "virtual-reply"

    SessionTaskManager.add_callback(first, ["physical-reply", "virtual-reply"], callback)
    await SessionTaskManager.check(first)
    await SessionTaskManager.check(second)

    remaining = bool(SessionTaskManager._callback_list)
    SessionTaskManager._callback_list.clear()
    return called == 2 and remaining


async def _test_callback_once_is_consumed_across_aliases():
    """显式一次性 callback 在任一别名首次命中后应整体失效。"""
    SessionTaskManager._callback_list.clear()
    called = 0

    async def callback(_session):
        nonlocal called
        called += 1

    first = MockMessageSession("1")
    await first.async_init("1")
    first.session_info.reply_id = "physical-reply"
    second = MockMessageSession("1")
    await second.async_init("1")
    second.session_info.reply_id = "virtual-reply"

    SessionTaskManager.add_callback(first, ["physical-reply", "virtual-reply"], callback, once=True)
    await SessionTaskManager.check(first)
    await SessionTaskManager.check(second)
    remaining = bool(SessionTaskManager._callback_list)
    SessionTaskManager._callback_list.clear()
    return called == 1 and not remaining


async def _test_reused_callback_keeps_independent_registration():
    """同一个函数对象用于两次独立发送时，命中一组不能删除另一组。"""
    SessionTaskManager._callback_list.clear()
    called = []

    async def callback(session):
        called.append(session.session_info.reply_id)

    first = MockMessageSession("1")
    await first.async_init("1")
    first.session_info.reply_id = "message-one"

    second = MockMessageSession("1")
    await second.async_init("1")
    second.session_info.reply_id = "message-two"

    first_key = SessionTaskManager.add_callback(first, "message-one", callback)
    second_key = SessionTaskManager.add_callback(second, "message-two", callback)
    await SessionTaskManager.check(first)
    first_remaining = set(SessionTaskManager._callback_list)
    await SessionTaskManager.check(second)

    remaining = set(SessionTaskManager._callback_list)
    SessionTaskManager._callback_list.clear()
    return (
        called == ["message-one", "message-two"]
        and first_remaining == {first_key, second_key}
        and remaining == {first_key, second_key}
    )


async def _test_shared_callback_fallback_is_not_guessed():
    """两次发送共享同一 bot_id fallback 时不得按注册顺序猜测。"""
    SessionTaskManager._callback_list.clear()
    called = []

    async def first_callback(_session):
        called.append("first")

    async def second_callback(_session):
        called.append("second")

    reply = MockMessageSession("1")
    await reply.async_init("1")
    reply.session_info.reply_id = "shared-bot-id"

    SessionTaskManager.add_callback(reply, "message-one", first_callback, fallback_ids="shared-bot-id")
    SessionTaskManager.add_callback(reply, "message-two", second_callback, fallback_ids="shared-bot-id")
    ambiguous_handled = await SessionTaskManager.check(reply)
    both_remain = len(SessionTaskManager._callback_list) == 2

    reply.session_info.reply_id = "message-one"
    first_handled = await SessionTaskManager.check(reply)
    reply.session_info.reply_id = "shared-bot-id"
    fallback_still_ambiguous = not await SessionTaskManager.check(reply)

    remaining = len(SessionTaskManager._callback_list)
    SessionTaskManager._callback_list.clear()
    return (
        not ambiguous_handled
        and both_remain
        and first_handled
        and fallback_still_ambiguous
        and called == ["first"]
        and remaining == 2
    )


async def _test_callback_registration_handle_survives_alias_collision():
    """相同虚拟 ID 的并发注册不能覆盖，物理 ID 回包后应各自命中。"""
    SessionTaskManager._callback_list.clear()
    called = []

    async def first_callback(_session):
        called.append("first")

    async def second_callback(_session):
        called.append("second")

    reply = MockMessageSession("1")
    await reply.async_init("1")
    first_key = SessionTaskManager.add_callback(reply, "shared-primary", first_callback)
    second_key = SessionTaskManager.add_callback(reply, "shared-primary", second_callback)
    try:
        reply.session_info.reply_id = "shared-primary"
        ambiguous_handled = await SessionTaskManager.check(reply)
        if ambiguous_handled or first_key == second_key or len(SessionTaskManager._callback_list) != 2:
            return False

        SessionTaskManager.extend_callback(first_key, "physical-one")
        SessionTaskManager.extend_callback(second_key, "physical-two")
        reply.session_info.reply_id = "physical-one"
        first_handled = await SessionTaskManager.check(reply)
        reply.session_info.reply_id = "physical-two"
        second_handled = await SessionTaskManager.check(reply)
        return first_handled and second_handled and called == ["first", "second"]
    finally:
        SessionTaskManager._callback_list.clear()


async def _test_pending_plain_callbacks_make_bot_fallback_ambiguous():
    """无按钮 callback 在发送回包前也须登记，避免 bot_id fallback 串线。"""
    from core.builtins.session.internal import MessageSession
    from core.exports import exports
    from core.i18n import Locale

    entered = asyncio.Event()
    release_sends = asyncio.Event()
    call_count = 0
    called = []

    class BlockingQueueServer:
        @classmethod
        async def client_send_message(cls, session_info, chain, **kwargs):
            nonlocal call_count
            call_index = call_count
            call_count += 1
            if call_count == 2:
                entered.set()
            await release_sends.wait()
            return {"message_id": [f"physical-{call_index}"]}

    async def first_callback(_session):
        called.append("first")

    async def second_callback(_session):
        called.append("second")

    session = SessionInfo(
        target_id="TEST|Group|pending-plain-callback",
        target_from="TEST|Group",
        client_name="TEST",
        sender_id="TEST|pending-plain-callback",
        bot_id="shared-bot-fallback",
        locale=Locale("zh_cn"),
        tmp={},
    )
    first = MessageSession(session)
    second = MessageSession(session)
    incoming = MessageSession(
        SessionInfo(
            target_id=session.target_id,
            target_from=session.target_from,
            client_name=session.client_name,
            sender_id=session.sender_id,
            reply_id="shared-bot-fallback",
            locale=session.locale,
            tmp={},
        )
    )
    SessionTaskManager._callback_list.clear()
    first_task = None
    second_task = None
    try:
        with patch.dict(exports, {"JobQueueServer": BlockingQueueServer}):
            first_task = asyncio.create_task(first.send_message("one", callback=first_callback))
            second_task = asyncio.create_task(second.send_message("two", callback=second_callback))
            await asyncio.wait_for(entered.wait(), timeout=0.5)
            ambiguous_handled = await SessionTaskManager.check(incoming)
            if ambiguous_handled or called or len(SessionTaskManager._callback_list) != 2:
                return False
            release_sends.set()
            await asyncio.gather(first_task, second_task)

        incoming.session_info.reply_id = "physical-0"
        first_handled = await SessionTaskManager.check(incoming)
        incoming.session_info.reply_id = "physical-1"
        second_handled = await SessionTaskManager.check(incoming)
        return first_handled and second_handled and called == ["first", "second"]
    finally:
        release_sends.set()
        pending = [task for task in (first_task, second_task) if task and not task.done()]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        SessionTaskManager._callback_list.clear()


async def _test_callback_primary_id_beats_fallback():
    """一个注册的主 ID 与另一注册 fallback 重合时，主 ID 必须优先。"""
    SessionTaskManager._callback_list.clear()
    called = []

    async def primary_callback(_session):
        called.append("primary")

    async def fallback_callback(_session):
        called.append("fallback")

    reply = MockMessageSession("1")
    await reply.async_init("1")
    reply.session_info.reply_id = "shared-id"
    SessionTaskManager.add_callback(reply, "shared-id", primary_callback)
    SessionTaskManager.add_callback(reply, "other-id", fallback_callback, fallback_ids="shared-id")
    try:
        handled = await SessionTaskManager.check(reply)
        return handled and called == ["primary"] and len(SessionTaskManager._callback_list) == 2
    finally:
        SessionTaskManager._callback_list.clear()


async def _test_callback_ignores_missing_reply_id():
    """非回复消息不能以字符串化的 None 命中 callback。"""
    SessionTaskManager._callback_list.clear()
    called = False

    async def callback(_session):
        nonlocal called
        called = True

    msg = MockMessageSession("1")
    await msg.async_init("1")
    msg.session_info.reply_id = None
    SessionTaskManager.add_callback(msg, "None", callback)
    await SessionTaskManager.check(msg)

    remaining = bool(SessionTaskManager._callback_list)
    SessionTaskManager._callback_list.clear()
    return not called and remaining


async def _test_callback_is_scoped_by_message_channel():
    """相同平台消息 ID 在不同现实场景中不能覆盖或误命中 callback。"""
    from core.builtins.session.info import SessionInfo

    SessionTaskManager._callback_list.clear()
    called = []

    async def first_callback(_session):
        called.append("first")

    async def second_callback(_session):
        called.append("second")

    async def make(target: str):
        msg = MockMessageSession("1")
        msg.session_info = await SessionInfo.assign(
            target_id=target,
            target_from="TEST|Group",
            client_name="TEST",
            sender_id="TEST|callback-scope",
            sender_from="TEST",
        )
        msg.session_info.reply_id = 42
        return msg

    first = await make("TEST|Group|callback-scope-one")
    second = await make("TEST|Group|callback-scope-two")
    first_key = SessionTaskManager.add_callback(first, "42", first_callback)
    SessionTaskManager.add_callback(second, "42", second_callback)
    try:
        handled_second = await SessionTaskManager.check(second)
        first_still_registered = first_key in SessionTaskManager._callback_list
        handled_first = await SessionTaskManager.check(first)
        return handled_second and handled_first and first_still_registered and called == ["second", "first"]
    finally:
        SessionTaskManager._callback_list.clear()


async def _test_callback_finish_is_consumed_as_control_flow():
    """callback 调用 msg.finish() 的 SessionFinished 不得让队列 action 卡在 processing。"""
    from core.constants import SessionFinished

    SessionTaskManager._callback_list.clear()
    msg = MockMessageSession("1")
    await msg.async_init("1")
    msg.session_info.reply_id = "finish-callback"

    async def callback(_session):
        raise SessionFinished([])

    SessionTaskManager.add_callback(msg, "finish-callback", callback)
    try:
        return await SessionTaskManager.check(msg) and bool(SessionTaskManager._callback_list)
    finally:
        SessionTaskManager._callback_list.clear()


async def _test_callback_rejects_other_physical_sender():
    """普通 reply 必须与 callback 发送时的物理账号一致。"""
    from core.builtins.session.internal import MessageSession

    target_id = "TEST|Group|callback-owner"
    owner = MessageSession(
        await SessionInfo.assign(
            target_id=target_id,
            target_from="TEST|Group",
            client_name="TEST",
            sender_id="TEST|callback-owner",
            sender_from="TEST",
            reply_id="owner-message",
        )
    )
    attacker = MessageSession(
        await SessionInfo.assign(
            target_id=target_id,
            target_from="TEST|Group",
            client_name="TEST",
            sender_id="TEST|callback-attacker",
            sender_from="TEST",
            reply_id="owner-message",
        )
    )
    called = []

    async def callback(session):
        called.append(session.session_info.sender_id)

    SessionTaskManager._callback_list.clear()
    SessionTaskManager.add_callback(owner, "owner-message", callback)
    try:
        attacker_handled = await SessionTaskManager.check(attacker)
        still_registered = bool(SessionTaskManager._callback_list)
        owner_handled = await SessionTaskManager.check(owner)
        return (
            not attacker_handled
            and still_registered
            and owner_handled
            and called == [owner.session_info.sender_id]
            and bool(SessionTaskManager._callback_list)
        )
    finally:
        SessionTaskManager._callback_list.clear()


async def _test_callback_ttl_checked_on_use():
    """即使周期清理尚未运行，超过自身有效期的 callback 也不得执行。"""
    msg = MockMessageSession("1")
    await msg.async_init("1")
    msg.session_info.reply_id = "expired-callback"
    called = False

    async def callback(_session):
        nonlocal called
        called = True

    SessionTaskManager._callback_list.clear()
    callback_key = SessionTaskManager.add_callback(msg, "expired-callback", callback, timeout=10)
    SessionTaskManager._callback_list[callback_key]["ts"] -= 10
    try:
        handled = await SessionTaskManager.check(msg)
        return not handled and not called and not SessionTaskManager._callback_list
    finally:
        SessionTaskManager._callback_list.clear()


async def _test_repeatable_callback_is_serialized():
    """同一 callback 的连续触发应串行执行，并在完成后继续有效。"""
    SessionTaskManager._callback_list.clear()
    entered = asyncio.Event()
    release = asyncio.Event()
    active = 0
    max_active = 0
    called = 0

    async def callback(_session):
        nonlocal active, max_active, called
        active += 1
        max_active = max(max_active, active)
        called += 1
        if called == 1:
            entered.set()
            await release.wait()
        active -= 1

    first = MockMessageSession("1")
    await first.async_init("1")
    first.session_info.reply_id = "repeatable-callback"
    second = MockMessageSession("1")
    await second.async_init("1")
    second.session_info.reply_id = "repeatable-callback"
    SessionTaskManager.add_callback(first, "repeatable-callback", callback)
    first_task = asyncio.create_task(SessionTaskManager.check(first))
    second_task = None
    try:
        await asyncio.wait_for(entered.wait(), timeout=0.5)
        second_task = asyncio.create_task(SessionTaskManager.check(second))
        await asyncio.sleep(0)
        if second_task.done():
            return False
        release.set()
        handled = await asyncio.gather(first_task, second_task)
        return handled == [True, True] and called == 2 and max_active == 1 and bool(SessionTaskManager._callback_list)
    finally:
        release.set()
        pending = [task for task in (first_task, second_task) if task and not task.done()]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        SessionTaskManager._callback_list.clear()


async def _test_parser_rejects_blocked_wait_responder_before_task_check():
    """全局屏蔽用户不得完成场景内的 wait_anyone。"""
    from core.builtins.message.chain import MessageChain
    from core.builtins.parser.message import parser
    from core.builtins.session.internal import MessageSession

    target_id = "TEST|Group|blocked-wait-responder"
    waiting = MessageSession(
        await SessionInfo.assign(
            target_id=target_id,
            target_from="TEST|Group",
            client_name="TEST",
            sender_id="TEST|blocked-wait-owner",
            sender_from="TEST",
        )
    )
    incoming = MessageSession(
        await SessionInfo.assign(
            target_id=target_id,
            target_from="TEST|Group",
            client_name="TEST",
            sender_id="TEST|blocked-wait-responder",
            sender_from="TEST",
            messages=MessageChain.assign("answer"),
        )
    )
    await incoming.session_info.sender_union_info.switch_identity(trust=False)
    flag = asyncio.Event()
    SessionTaskManager._task_list.clear()
    SessionTaskManager.add_task(waiting, flag, all_=True, timeout=60)
    try:
        await parser(incoming)
        task_info = SessionTaskManager.get()[waiting.session_info.target_id]["all"][waiting]
        return not flag.is_set() and task_info["active"] and "result" not in task_info
    finally:
        SessionTaskManager._task_list.clear()


async def _test_parser_rejects_banned_callback_responder_before_task_check():
    """场景屏蔽用户不得继续触发封禁前登记的 callback。"""
    from core.builtins.message.chain import MessageChain
    from core.builtins.parser.message import parser
    from core.builtins.session.internal import MessageSession

    target_id = "TEST|Group|banned-callback-responder"
    sender_id = "TEST|banned-callback-responder"
    registered = MessageSession(
        await SessionInfo.assign(
            target_id=target_id,
            target_from="TEST|Group",
            client_name="TEST",
            sender_id=sender_id,
            sender_from="TEST",
        )
    )
    incoming = MessageSession(
        await SessionInfo.assign(
            target_id=target_id,
            target_from="TEST|Group",
            client_name="TEST",
            sender_id=sender_id,
            sender_from="TEST",
            reply_id="banned-callback",
            messages=MessageChain.assign("answer"),
        )
    )
    called = False

    async def callback(_session):
        nonlocal called
        called = True

    await incoming.session_info.target_union_info.config_banned_user(incoming.session_info.sender_union_id)
    SessionTaskManager._callback_list.clear()
    callback_key = SessionTaskManager.add_callback(registered, "banned-callback", callback)
    try:
        await parser(incoming)
        return not called and callback_key in SessionTaskManager._callback_list
    finally:
        SessionTaskManager._callback_list.clear()


async def _test_reply_task_normalizes_integer_reply_id():
    """平台提供整数 reply_id 时也应命中已字符串化的等待目标。"""
    SessionTaskManager._task_list.clear()
    waiting = MockMessageSession("prompt")
    await waiting.async_init("prompt")
    reply = MockMessageSession("reply")
    reply.session_info = waiting.session_info
    reply.session_info.reply_id = 123
    flag = asyncio.Event()
    SessionTaskManager.add_task(waiting, flag, reply=["123"])
    try:
        handled = await SessionTaskManager.check(reply)
        result = SessionTaskManager.get_result(waiting)
        return handled and flag.is_set() and result is reply
    finally:
        SessionTaskManager.remove_task(waiting)
        SessionTaskManager._task_list.clear()


async def _test_reply_task_preserves_comma_in_message_id():
    """消息 ID 自身含逗号时必须作为一个完整等待目标，不能按分隔符拆开。"""
    SessionTaskManager._task_list.clear()
    waiting = MockMessageSession("prompt")
    await waiting.async_init("prompt")
    reply = MockMessageSession("reply")
    await reply.async_init("reply")
    reply.session_info.reply_id = "event,with,comma"
    flag = asyncio.Event()
    SessionTaskManager.add_task(waiting, flag, reply=["event,with,comma"])
    try:
        handled = await SessionTaskManager.check(reply)
        result = SessionTaskManager.get_result(waiting)
        return handled and flag.is_set() and result is reply
    finally:
        SessionTaskManager.remove_task(waiting)
        SessionTaskManager._task_list.clear()


async def _test_send_message_restores_force_markdown_on_failure():
    """消息发送异常后应恢复原有 force_markdown 临时值。"""
    from core.builtins.session.info import SessionInfo
    from core.builtins.session.internal import MessageSession
    from core.exports import exports

    class FailingQueueServer:
        @classmethod
        async def client_send_message(cls, session_info, chain, **kwargs):
            raise RuntimeError("audit failure")

    session_info = await SessionInfo.assign(
        target_id="TEST|Group|force-markdown-failure",
        target_from="TEST|Group",
        client_name="TEST",
        sender_id="TEST|force-markdown-failure",
        sender_from="TEST",
    )
    session_info.tmp["force_markdown"] = "previous"
    msg = MessageSession(session_info)

    with patch.dict(exports, {"JobQueueServer": FailingQueueServer}):
        try:
            await msg.send_message("test", force_markdown=True)
        except RuntimeError:
            pass
        else:
            return False
    return session_info.tmp.get("force_markdown") == "previous"


async def _test_wait_next_message_registers_before_fast_reply():
    """提示发送完成后下一事件循环拍到达的回复不应落在等待任务登记之前。"""
    from core.builtins.session.info import SessionInfo
    from core.builtins.session.internal import MessageSession
    from core.constants import WaitCancelException

    class FastReplySession(MessageSession):
        async def send_message(self, *args, **kwargs):
            await SessionTaskManager.check(self)
            return object()

        async def end_typing(self):
            return None

    SessionTaskManager._task_list.clear()
    session_info = await SessionInfo.assign(
        target_id="TEST|Group|fast-reply",
        target_from="TEST|Group",
        client_name="TEST",
        sender_id="TEST|fast-reply",
        sender_from="TEST",
    )
    msg = FastReplySession(session_info)
    try:
        result = await msg.wait_next_message("prompt", timeout=0.05)
        return result is msg
    except WaitCancelException:
        return False
    finally:
        SessionTaskManager._task_list.clear()


async def _test_wait_confirm_registers_before_reaction_roundtrip():
    """添加确认反应发生网络让出时，立即到达的文本确认仍应命中等待任务。"""
    from core.builtins.message.chain import MessageChain
    from core.builtins.session.info import SessionInfo
    from core.builtins.session.internal import MessageSession
    from core.constants import WaitCancelException

    class FastConfirmSession(MessageSession):
        async def send_message(self, *args, **kwargs):
            await SessionTaskManager.check(self)
            return type("Sent", (), {"message_id": ["prompt"]})()

        async def end_typing(self):
            return None

        async def _add_confirm_reaction(self, message_id):
            await asyncio.sleep(0)

    SessionTaskManager._task_list.clear()
    session_info = await SessionInfo.assign(
        target_id="TEST|Group|fast-confirm",
        target_from="TEST|Group",
        client_name="TEST",
        sender_id="TEST|fast-confirm",
        sender_from="TEST",
        messages=MessageChain.assign("是"),
        features=Features(support_reaction=True),
    )
    msg = FastConfirmSession(session_info)
    try:
        return await msg.wait_confirm("prompt", delete=False, timeout=0.05)
    except WaitCancelException:
        return False
    finally:
        SessionTaskManager._task_list.clear()


async def _test_wait_reply_registers_before_send_returns():
    """提示已在平台显示但发送 action 尚未回包时，快速引用回复不应丢失。"""
    from core.builtins.session.internal import MessageSession

    check_task_holder = {}

    class FastReplySession(MessageSession):
        async def send_message(self, *args, **kwargs):
            check_task_holder["task"] = asyncio.create_task(SessionTaskManager.check(incoming))
            await asyncio.sleep(0)
            return type("Sent", (), {"message_id": ["fast-reply-prompt"]})()

        async def end_typing(self):
            return None

    session_info = await SessionInfo.assign(
        target_id="TEST|Group|fast-reply-id",
        target_from="TEST|Group",
        client_name="TEST",
        sender_id="TEST|fast-reply-id",
        sender_from="TEST",
        features=Features(support_quote=True),
    )
    incoming = MessageSession(
        await SessionInfo.assign(
            target_id=session_info.target_id,
            target_from=session_info.target_from,
            client_name=session_info.client_name,
            sender_id=session_info.sender_id,
            sender_from=session_info.sender_from,
            reply_id="fast-reply-prompt",
        )
    )
    msg = FastReplySession(session_info)
    SessionTaskManager._task_list.clear()
    try:
        result = await msg.wait_reply("prompt", delete=False, timeout=0.5)
        handled = await check_task_holder["task"] if "task" in check_task_holder else False
        return result is incoming and handled and not SessionTaskManager.get()
    finally:
        check_task = check_task_holder.get("task")
        if check_task and not check_task.done():
            check_task.cancel()
        SessionTaskManager._task_list.clear()


async def _test_ready_reply_is_not_blocked_by_earlier_pending_reply():
    """较早 pending 的 reply task 不得阻塞后登记但已 ready 的精确目标。"""
    from core.builtins.session.internal import MessageSession

    class HeldIncoming(MessageSession):
        hold_calls = 0
        release_calls = 0

        async def hold(self):
            self.hold_calls += 1

        async def release(self):
            self.release_calls += 1

    target_id = "TEST|Group|pending-reply-order"
    first = MessageSession(
        await SessionInfo.assign(
            target_id=target_id,
            target_from="TEST|Group",
            client_name="TEST",
            sender_id="TEST|pending-reply-order",
            sender_from="TEST",
        )
    )
    second = MessageSession(
        await SessionInfo.assign(
            target_id=target_id,
            target_from="TEST|Group",
            client_name="TEST",
            sender_id=first.session_info.sender_id,
            sender_from="TEST",
        )
    )
    incoming = HeldIncoming(
        await SessionInfo.assign(
            target_id=target_id,
            target_from="TEST|Group",
            client_name="TEST",
            sender_id=first.session_info.sender_id,
            sender_from="TEST",
            reply_id="ready-target",
        )
    )
    first_flag = asyncio.Event()
    second_flag = asyncio.Event()
    SessionTaskManager._task_list.clear()
    SessionTaskManager.add_task(first, first_flag, reply_pending=True, timeout=60)
    SessionTaskManager.add_task(second, second_flag, reply="ready-target", timeout=60)
    try:
        handled = await asyncio.wait_for(SessionTaskManager.check(incoming), timeout=0.2)
        first_info = SessionTaskManager.get()[first.session_info.target_id][first.session_info.sender_id][first]
        second_info = SessionTaskManager.get()[second.session_info.target_id][second.session_info.sender_id][second]
        await second.release_execution_resources()
        return (
            handled
            and not first_flag.is_set()
            and first_info["active"]
            and second_flag.is_set()
            and second_info.get("result") is incoming
            and incoming.hold_calls == 1
            and incoming.release_calls == 1
        )
    finally:
        SessionTaskManager.remove_task(first)
        SessionTaskManager.remove_task(second)
        SessionTaskManager._task_list.clear()


async def _test_wait_reply_send_failure_unblocks_pending_parser():
    """reply 提示发送失败时，已到达的引用消息不得永远卡在 reply_ready。"""
    from core.builtins.session.internal import MessageSession

    check_task_holder = {}

    class IncomingSession(MessageSession):
        hold_calls = 0

        async def hold(self):
            self.hold_calls += 1

    incoming = IncomingSession(
        await SessionInfo.assign(
            target_id="TEST|Group|reply-send-failure",
            target_from="TEST|Group",
            client_name="TEST",
            sender_id="TEST|reply-send-failure",
            sender_from="TEST",
            reply_id="unrelated-reply",
        )
    )

    class FailingReplySession(MessageSession):
        async def send_message(self, *args, **kwargs):
            check_task_holder["task"] = asyncio.create_task(SessionTaskManager.check(incoming))
            await asyncio.sleep(0)
            raise RuntimeError("send failed")

        async def end_typing(self):
            return None

    waiting = FailingReplySession(
        await SessionInfo.assign(
            target_id=incoming.session_info.target_id,
            target_from=incoming.session_info.target_from,
            client_name=incoming.session_info.client_name,
            sender_id=incoming.session_info.sender_id,
            sender_from=incoming.session_info.sender_from,
            features=Features(support_quote=True),
        )
    )
    SessionTaskManager._task_list.clear()
    try:
        try:
            await waiting.wait_reply("prompt", timeout=None)
        except RuntimeError:
            pass
        else:
            return False
        check_task = check_task_holder.get("task")
        return (
            check_task is not None
            and not await asyncio.wait_for(check_task, timeout=0.2)
            and not SessionTaskManager.get()
            and incoming.hold_calls == 0
        )
    finally:
        check_task = check_task_holder.get("task")
        if check_task and not check_task.done():
            check_task.cancel()
        SessionTaskManager._task_list.clear()


async def _test_wait_reply_timeout_covers_pending_send():
    """wait_reply 的 timeout 必须覆盖发送阶段，并唤醒已等待 reply_ready 的 parser。"""
    from core.builtins.session.internal import MessageSession
    from core.constants import WaitCancelException

    check_task_holder = {}
    send_entered = asyncio.Event()
    never_finish = asyncio.Event()
    send_cancelled = False

    class IncomingSession(MessageSession):
        hold_calls = 0

        async def hold(self):
            self.hold_calls += 1

    incoming = IncomingSession(
        await SessionInfo.assign(
            target_id="TEST|Group|reply-send-timeout",
            target_from="TEST|Group",
            client_name="TEST",
            sender_id="TEST|reply-send-timeout",
            sender_from="TEST",
            reply_id="unrelated-reply",
        )
    )

    class BlockingReplySession(MessageSession):
        async def send_message(self, *args, **kwargs):
            nonlocal send_cancelled
            check_task_holder["task"] = asyncio.create_task(SessionTaskManager.check(incoming))
            send_entered.set()
            try:
                await never_finish.wait()
            except asyncio.CancelledError:
                send_cancelled = True
                raise

        async def end_typing(self):
            return None

    waiting = BlockingReplySession(
        await SessionInfo.assign(
            target_id=incoming.session_info.target_id,
            target_from=incoming.session_info.target_from,
            client_name=incoming.session_info.client_name,
            sender_id=incoming.session_info.sender_id,
            sender_from=incoming.session_info.sender_from,
            features=Features(support_quote=True),
        )
    )
    SessionTaskManager._task_list.clear()
    try:
        try:
            await asyncio.wait_for(waiting.wait_reply("prompt", timeout=0.05), timeout=0.3)
        except WaitCancelException:
            pass
        except asyncio.TimeoutError:
            return False
        else:
            return False

        check_task = check_task_holder.get("task")
        return (
            send_entered.is_set()
            and send_cancelled
            and check_task is not None
            and not await asyncio.wait_for(check_task, timeout=0.2)
            and not SessionTaskManager.get()
            and incoming.hold_calls == 0
        )
    finally:
        never_finish.set()
        check_task = check_task_holder.get("task")
        if check_task and not check_task.done():
            check_task.cancel()
        SessionTaskManager._task_list.clear()


async def _test_wait_reply_timeout_is_single_deadline():
    """发送提示耗时须从后续等待回复的预算中扣除。"""
    from core.builtins.session.internal import MessageSession
    from core.constants import WaitCancelException

    prompt_id = "single-deadline-prompt"

    class SlowReplySession(MessageSession):
        async def send_message(self, *args, **kwargs):
            await asyncio.sleep(0.1)
            return type("Sent", (), {"message_id": [prompt_id]})()

        async def end_typing(self):
            return None

    waiting = SlowReplySession(
        await SessionInfo.assign(
            target_id="TEST|Group|reply-single-deadline",
            target_from="TEST|Group",
            client_name="TEST",
            sender_id="TEST|reply-single-deadline",
            sender_from="TEST",
            features=Features(support_quote=True),
        )
    )
    incoming = MessageSession(
        await SessionInfo.assign(
            target_id=waiting.session_info.target_id,
            target_from=waiting.session_info.target_from,
            client_name=waiting.session_info.client_name,
            sender_id=waiting.session_info.sender_id,
            sender_from=waiting.session_info.sender_from,
            reply_id=prompt_id,
        )
    )

    async def delayed_reply():
        await asyncio.sleep(0.25)
        return await SessionTaskManager.check(incoming)

    SessionTaskManager._task_list.clear()
    reply_task = asyncio.create_task(delayed_reply())
    try:
        try:
            await asyncio.wait_for(waiting.wait_reply("prompt", timeout=0.2), timeout=0.4)
        except WaitCancelException:
            pass
        except asyncio.TimeoutError:
            return False
        else:
            return False
        return not await asyncio.wait_for(reply_task, timeout=0.2) and not SessionTaskManager.get()
    finally:
        if not reply_task.done():
            reply_task.cancel()
            await asyncio.gather(reply_task, return_exceptions=True)
        SessionTaskManager._task_list.clear()


async def _test_wait_reply_none_timeout_keeps_pending_send():
    """timeout=None 必须保留无限等待语义，直到调用方取消。"""
    from core.builtins.session.internal import MessageSession

    send_entered = asyncio.Event()
    never_finish = asyncio.Event()
    send_cancelled = False

    class BlockingReplySession(MessageSession):
        async def send_message(self, *args, **kwargs):
            nonlocal send_cancelled
            send_entered.set()
            try:
                await never_finish.wait()
            except asyncio.CancelledError:
                send_cancelled = True
                raise

        async def end_typing(self):
            return None

    waiting = BlockingReplySession(
        await SessionInfo.assign(
            target_id="TEST|Group|reply-no-timeout",
            target_from="TEST|Group",
            client_name="TEST",
            sender_id="TEST|reply-no-timeout",
            sender_from="TEST",
            features=Features(support_quote=True),
        )
    )
    SessionTaskManager._task_list.clear()
    wait_task = asyncio.create_task(waiting.wait_reply("prompt", timeout=None))
    try:
        await asyncio.wait_for(send_entered.wait(), timeout=0.2)
        await asyncio.sleep(0.05)
        still_pending = not wait_task.done() and bool(SessionTaskManager.get())
        wait_task.cancel()
        await asyncio.gather(wait_task, return_exceptions=True)
        return still_pending and send_cancelled and not SessionTaskManager.get()
    finally:
        never_finish.set()
        if not wait_task.done():
            wait_task.cancel()
            await asyncio.gather(wait_task, return_exceptions=True)
        SessionTaskManager._task_list.clear()


async def _test_wait_reply_deletes_prompt_when_reply_registration_is_lost():
    """发送成功后若 pending task 已失效，delete=True 仍须撤回无法交互的提示。"""
    from core.builtins.session.internal import MessageSession
    from core.constants import WaitCancelException

    delete_calls = 0

    class Sent:
        message_id = ["orphaned-wait-reply-prompt"]

        async def delete(self):
            nonlocal delete_calls
            delete_calls += 1

    class LostRegistrationSession(MessageSession):
        async def send_message(self, *args, **kwargs):
            SessionTaskManager.remove_task(self)
            return Sent()

        async def end_typing(self):
            return None

    waiting = LostRegistrationSession(
        await SessionInfo.assign(
            target_id="TEST|Group|reply-registration-lost",
            target_from="TEST|Group",
            client_name="TEST",
            sender_id="TEST|reply-registration-lost",
            sender_from="TEST",
            features=Features(support_quote=True),
        )
    )
    SessionTaskManager._task_list.clear()
    try:
        try:
            await waiting.wait_reply("prompt", delete=True, timeout=None)
        except WaitCancelException:
            pass
        else:
            return False
        return delete_calls == 1 and not SessionTaskManager.get()
    finally:
        SessionTaskManager._task_list.clear()


async def _test_cancelled_wait_reply_deletes_sent_prompt():
    """调用方取消已经发出提示的 wait_reply 时，delete=True 不应遗留提示。"""
    from core.builtins.session.internal import MessageSession

    send_returned = asyncio.Event()
    delete_calls = 0

    class Sent:
        message_id = ["cancelled-wait-reply-prompt"]

        async def delete(self):
            nonlocal delete_calls
            delete_calls += 1

    class DeletableReplySession(MessageSession):
        async def send_message(self, *args, **kwargs):
            send_returned.set()
            return Sent()

        async def end_typing(self):
            return None

    waiting = DeletableReplySession(
        await SessionInfo.assign(
            target_id="TEST|Group|reply-cancel-delete",
            target_from="TEST|Group",
            client_name="TEST",
            sender_id="TEST|reply-cancel-delete",
            sender_from="TEST",
            features=Features(support_quote=True),
        )
    )
    SessionTaskManager._task_list.clear()
    wait_task = asyncio.create_task(waiting.wait_reply("prompt", delete=True, timeout=None))
    try:
        await asyncio.wait_for(send_returned.wait(), timeout=0.2)
        await asyncio.sleep(0)
        wait_task.cancel()
        result = (await asyncio.gather(wait_task, return_exceptions=True))[0]
        return isinstance(result, asyncio.CancelledError) and delete_calls == 1 and not SessionTaskManager.get()
    finally:
        if not wait_task.done():
            wait_task.cancel()
            await asyncio.gather(wait_task, return_exceptions=True)
        SessionTaskManager._task_list.clear()


async def _test_wait_reply_committed_result_beats_timeout_observation():
    """incoming 已提交 result 后，即使 deadline 同拍触发也必须返回已消费的回复。"""
    from core.builtins.session.internal import MessageSession

    prompt_id = "committed-result-prompt"
    check_task_holder = {}

    class TimeoutAfterBody:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            if exc_type is None:
                raise TimeoutError
            return False

    class HeldIncoming(MessageSession):
        hold_calls = 0
        release_calls = 0

        async def hold(self):
            self.hold_calls += 1

        async def release(self):
            self.release_calls += 1

    waiting_info = await SessionInfo.assign(
        target_id="TEST|Group|reply-timeout-result-race",
        target_from="TEST|Group",
        client_name="TEST",
        sender_id="TEST|reply-timeout-result-race",
        sender_from="TEST",
        features=Features(support_quote=True),
    )
    incoming = HeldIncoming(
        await SessionInfo.assign(
            target_id=waiting_info.target_id,
            target_from=waiting_info.target_from,
            client_name=waiting_info.client_name,
            sender_id=waiting_info.sender_id,
            sender_from=waiting_info.sender_from,
            reply_id=prompt_id,
        )
    )

    class RacingReplySession(MessageSession):
        async def send_message(self, *args, **kwargs):
            check_task_holder["task"] = asyncio.create_task(SessionTaskManager.check(incoming))
            await asyncio.sleep(0)
            return type("Sent", (), {"message_id": [prompt_id]})()

        async def end_typing(self):
            return None

    waiting = RacingReplySession(waiting_info)
    SessionTaskManager._task_list.clear()
    try:
        with patch("core.builtins.session.internal.asyncio.timeout", return_value=TimeoutAfterBody()):
            result = await waiting.wait_reply("prompt", timeout=0.1)
        handled = await check_task_holder["task"]
        await waiting.release_execution_resources()
        return (
            result is incoming
            and handled
            and incoming.hold_calls == 1
            and incoming.release_calls == 1
            and not SessionTaskManager.get()
        )
    finally:
        check_task = check_task_holder.get("task")
        if check_task and not check_task.done():
            check_task.cancel()
            await asyncio.gather(check_task, return_exceptions=True)
        SessionTaskManager._task_list.clear()


async def _test_wait_reply_delete_failure_does_not_mask_cancellation():
    """撤回失败只能记录日志，不能把 wait_reply 的取消结果改成删除异常。"""
    from core.builtins.session.internal import MessageSession
    from core.constants import WaitCancelException

    class Sent:
        message_id = ["failed-delete-wait-reply-prompt"]

        async def delete(self):
            raise RuntimeError("delete failed")

    class LostRegistrationSession(MessageSession):
        async def send_message(self, *args, **kwargs):
            SessionTaskManager.remove_task(self)
            return Sent()

        async def end_typing(self):
            return None

    waiting = LostRegistrationSession(
        await SessionInfo.assign(
            target_id="TEST|Group|reply-delete-failure",
            target_from="TEST|Group",
            client_name="TEST",
            sender_id="TEST|reply-delete-failure",
            sender_from="TEST",
            features=Features(support_quote=True),
        )
    )
    SessionTaskManager._task_list.clear()
    try:
        try:
            await waiting.wait_reply("prompt", delete=True, timeout=None)
        except WaitCancelException:
            return not SessionTaskManager.get()
        except RuntimeError:
            return False
        return False
    finally:
        SessionTaskManager._task_list.clear()


async def _test_wait_task_follows_sender_union_merge():
    """Sender Union 改为全新 ID 后，原物理账号仍须命中自己登记的 waiter。"""
    target_id = "WAITMERGES|Group|1"
    sender_a = "WAITMERGES|A"
    sender_b = "WAITMERGES|B"
    waiting = await _make_held_session(target_id, sender_a, "WAITMERGES")
    other = await SenderUnionInfo.resolve_union(sender_b)
    flag = asyncio.Event()
    SessionTaskManager._task_list.clear()
    SessionTaskManager.add_task(waiting, flag, timeout=60)
    try:
        merged = await waiting.session_info.sender_union_info.merge_union(other)
        incoming = await _make_held_session(target_id, sender_a, "WAITMERGES")
        handled = await SessionTaskManager.check(incoming)
        result = SessionTaskManager.get_result(waiting)
        await waiting.release_execution_resources()
        return (
            merged is not None
            and handled
            and flag.is_set()
            and result is incoming
            and incoming.hold_calls == 1
            and incoming.release_calls == 1
        )
    finally:
        SessionTaskManager.remove_task(waiting)
        SessionTaskManager._task_list.clear()


async def _test_wait_task_follows_sender_unbind_without_old_owner_takeover():
    """被拆出的账号保留 waiter，留在旧 Sender Union 的账号不得接管。"""
    target_id = "WAITUNBINDS|Group|1"
    sender_a = "WAITUNBINDS|A"
    sender_b = "WAITUNBINDS|B"
    sender_union = await SenderUnionInfo.resolve_union(sender_a)
    if not await sender_union.bind_id(sender_b):
        return False
    waiting = await _make_held_session(target_id, sender_b, "WAITUNBINDS")
    flag = asyncio.Event()
    SessionTaskManager._task_list.clear()
    SessionTaskManager.add_task(waiting, flag, timeout=60)
    try:
        if not await sender_union.unbind_id(sender_b):
            return False
        old_owner = await _make_held_session(target_id, sender_a, "WAITUNBINDS")
        original_owner = await _make_held_session(target_id, sender_b, "WAITUNBINDS")
        old_handled = await SessionTaskManager.check(old_owner)
        original_handled = await SessionTaskManager.check(original_owner)
        await waiting.release_execution_resources()
        return (
            not old_handled
            and original_handled
            and flag.is_set()
            and old_owner.hold_calls == 0
            and original_owner.hold_calls == 1
            and original_owner.release_calls == 1
        )
    finally:
        SessionTaskManager.remove_task(waiting)
        SessionTaskManager._task_list.clear()


async def _test_wait_task_follows_target_merge_and_current_channel():
    """Target merge 后跟随物理场景；只有随后明确同通道的 sibling 才能共享 waiter。"""
    target_a = "WAITMERGETA|Group|1"
    target_b = "WAITMERGETB|Group|2"
    sender_id = "WAITMERGET|USER"
    first_waiting = await _make_held_session(target_a, sender_id, "WAITMERGETA")
    target_b_union = await TargetUnionInfo.resolve_union(target_b)
    first_flag = asyncio.Event()
    SessionTaskManager._task_list.clear()
    SessionTaskManager.add_task(first_waiting, first_flag, timeout=60)
    try:
        merged = await first_waiting.session_info.target_union_info.merge_union(target_b_union)
        if merged is None:
            return False
        separated = await _make_held_session(target_b, sender_id, "WAITMERGETB")
        original = await _make_held_session(target_a, sender_id, "WAITMERGETA")
        separated_handled = await SessionTaskManager.check(separated)
        original_handled = await SessionTaskManager.check(original)
        await first_waiting.release_execution_resources()
        if separated_handled or not original_handled or separated.hold_calls != 0:
            return False
        SessionTaskManager.remove_task(first_waiting)

        second_waiting = await _make_held_session(target_a, sender_id, "WAITMERGETA")
        second_flag = asyncio.Event()
        SessionTaskManager.add_task(second_waiting, second_flag, timeout=60)
        target_a_bind = await TargetUnionBind.get(target_id=target_a)
        await TargetUnionBind.filter(target_id=target_b).update(channel_id=target_a_bind.channel_id)
        shared = await _make_held_session(target_b, sender_id, "WAITMERGETB")
        shared_handled = await SessionTaskManager.check(shared)
        await second_waiting.release_execution_resources()
        SessionTaskManager.remove_task(second_waiting)
        return (
            first_flag.is_set()
            and second_flag.is_set()
            and shared_handled
            and original.hold_calls == 1
            and original.release_calls == 1
            and shared.hold_calls == 1
            and shared.release_calls == 1
        )
    finally:
        SessionTaskManager.remove_task(first_waiting)
        SessionTaskManager._task_list.clear()


async def _test_wait_task_follows_target_unbind_without_old_channel_takeover():
    """被拆出的物理场景保留 waiter，旧 Target Union／channel 不得接管。"""
    target_a = "WAITUNBINDTA|Group|1"
    target_b = "WAITUNBINDTB|Group|2"
    sender_id = "WAITUNBINDT|USER"
    target_union = await TargetUnionInfo.resolve_union(target_a)
    if not await target_union.bind_id(target_b):
        return False
    await TargetUnionBind.filter(target_id=target_b).update(channel_id=1)
    waiting = await _make_held_session(target_b, sender_id, "WAITUNBINDTB")
    flag = asyncio.Event()
    SessionTaskManager._task_list.clear()
    SessionTaskManager.add_task(waiting, flag, all_=True, timeout=60)
    try:
        if not await target_union.unbind_id(target_b):
            return False
        old_channel = await _make_held_session(target_a, sender_id, "WAITUNBINDTA")
        original_target = await _make_held_session(target_b, sender_id, "WAITUNBINDTB")
        old_handled = await SessionTaskManager.check(old_channel)
        original_handled = await SessionTaskManager.check(original_target)
        await waiting.release_execution_resources()
        return (
            not old_handled
            and original_handled
            and flag.is_set()
            and old_channel.hold_calls == 0
            and original_target.hold_calls == 1
            and original_target.release_calls == 1
        )
    finally:
        SessionTaskManager.remove_task(waiting, all_=True)
        SessionTaskManager._task_list.clear()


async def _test_wait_task_follows_target_rechannel_without_old_channel_takeover():
    """物理场景重新分配通道后，all_ waiter 也应跟随它而不是留在旧通道。"""
    target_a = "WAITCHANNELA|Group|1"
    target_b = "WAITCHANNELB|Group|2"
    sender_id = "WAITCHANNEL|USER"
    target_union = await TargetUnionInfo.resolve_union(target_a)
    if not await target_union.bind_id(target_b):
        return False
    await TargetUnionBind.filter(target_id=target_b).update(channel_id=1)
    waiting = await _make_held_session(target_b, sender_id, "WAITCHANNELB")
    flag = asyncio.Event()
    SessionTaskManager._task_list.clear()
    SessionTaskManager.add_task(waiting, flag, all_=True, timeout=60)
    try:
        await TargetUnionBind.filter(target_id=target_b).update(channel_id=2)
        old_channel = await _make_held_session(target_a, sender_id, "WAITCHANNELA")
        original_target = await _make_held_session(target_b, sender_id, "WAITCHANNELB")
        old_handled = await SessionTaskManager.check(old_channel)
        original_handled = await SessionTaskManager.check(original_target)
        await waiting.release_execution_resources()
        return (
            not old_handled
            and original_handled
            and flag.is_set()
            and old_channel.hold_calls == 0
            and original_target.hold_calls == 1
            and original_target.release_calls == 1
        )
    finally:
        SessionTaskManager.remove_task(waiting, all_=True)
        SessionTaskManager._task_list.clear()


async def _test_reply_wait_is_scoped_to_physical_platform_scene():
    """同现实通道的另一平台即使 message_id 碰撞，也不得命中本平台 wait_reply。"""
    target_a = "WAITREPLYSA|Group|1"
    target_b = "WAITREPLYSB|Group|2"
    sender_a = "WAITREPLYSA|USER"
    sender_b = "WAITREPLYSB|USER"
    target_union = await TargetUnionInfo.resolve_union(target_a)
    sender_union = await SenderUnionInfo.resolve_union(sender_a)
    if not await target_union.bind_id(target_b) or not await sender_union.bind_id(sender_b):
        return False
    await TargetUnionBind.filter(target_id=target_b).update(channel_id=1)
    waiting = await _make_held_session(target_a, sender_a, "WAITREPLYSA")
    flag = asyncio.Event()
    SessionTaskManager._task_list.clear()
    SessionTaskManager.add_task(waiting, flag, reply="same-message-id", timeout=60)
    try:
        other_platform = await _make_held_session(
            target_b,
            sender_b,
            "WAITREPLYSB",
            reply_id="same-message-id",
        )
        original_platform = await _make_held_session(
            target_a,
            sender_a,
            "WAITREPLYSA",
            reply_id="same-message-id",
        )
        other_handled = await SessionTaskManager.check(other_platform)
        original_handled = await SessionTaskManager.check(original_platform)
        await waiting.release_execution_resources()
        return (
            not other_handled
            and original_handled
            and flag.is_set()
            and other_platform.hold_calls == 0
            and original_platform.hold_calls == 1
            and original_platform.release_calls == 1
        )
    finally:
        SessionTaskManager.remove_task(waiting)
        SessionTaskManager._task_list.clear()


async def _test_wait_task_physical_index_survives_refresh_after_topology_change():
    """等待会话刷新到新 Union／channel 后，set_task_reply 与 remove 仍须命中稳定 bucket。"""
    target_a = "WAITREFRESHA|Group|1"
    target_b = "WAITREFRESHB|Group|2"
    sender_a = "WAITREFRESHA|USER"
    sender_b = "WAITREFRESHB|USER"
    target_union = await TargetUnionInfo.resolve_union(target_a)
    sender_union = await SenderUnionInfo.resolve_union(sender_a)
    if not await target_union.bind_id(target_b) or not await sender_union.bind_id(sender_b):
        return False
    await TargetUnionBind.filter(target_id=target_b).update(channel_id=1)
    waiting = await _make_held_session(target_b, sender_b, "WAITREFRESHB")
    flag = asyncio.Event()
    SessionTaskManager._task_list.clear()
    SessionTaskManager.add_task(waiting, flag, reply_pending=True, timeout=60)
    try:
        if not await sender_union.unbind_id(sender_b):
            return False
        await TargetUnionBind.filter(target_id=target_b).update(channel_id=2)
        await waiting.session_info.refresh_info()
        reply_set = SessionTaskManager.set_task_reply(waiting, "stable-reply")
        removed = SessionTaskManager.remove_task(waiting)
        return (
            reply_set
            and removed is not None
            and removed["reply"] == ("stable-reply",)
            and removed["reply_ready"].is_set()
            and not SessionTaskManager.get()
        )
    finally:
        SessionTaskManager.remove_task(waiting)
        SessionTaskManager._task_list.clear()


async def _test_task_bg_check_timeout():
    """测试 SessionTaskManager.bg_check() 超时处理"""
    try:
        SessionTaskManager._task_list.clear()

        msg = MockMessageSession("~test")
        await msg.async_init("~test")

        flag = asyncio.Event()
        SessionTaskManager.add_task(msg, flag, timeout=0)

        await asyncio.sleep(0.1)

        await SessionTaskManager.bg_check()

        task_list = SessionTaskManager.get()
        session_info = msg.session_info
        task_info = task_list[session_info.target_id][session_info.sender_id][msg]
        if task_info["active"]:
            return False

        if not flag.is_set():
            return False

        SessionTaskManager._task_list.clear()

        return True
    except Exception:
        return False


async def _test_task_remove_prunes_indexes():
    """等待完成后应释放 MessageSession 及空的父级索引。"""
    try:
        SessionTaskManager._task_list.clear()
        msg = MockMessageSession("~test")
        await msg.async_init("~test")
        flag = asyncio.Event()
        SessionTaskManager.add_task(msg, flag, timeout=60)

        task_info = SessionTaskManager.remove_task(msg)
        return task_info is not None and not SessionTaskManager.get()
    finally:
        SessionTaskManager._task_list.clear()


async def _test_inactive_task_does_not_capture_message():
    """已完成但尚待等待协程回收的任务不得被下一条消息覆盖结果。"""
    try:
        SessionTaskManager._task_list.clear()
        waiting = MockMessageSession("~test")
        await waiting.async_init("~test")
        first_result = MockMessageSession("first")
        await first_result.async_init("first")
        second_result = MockMessageSession("second")
        await second_result.async_init("second")

        flag = asyncio.Event()
        SessionTaskManager.add_task(waiting, flag, timeout=60)
        task_info = SessionTaskManager.get()[waiting.session_info.target_id][waiting.session_info.sender_id][waiting]
        task_info["active"] = False
        task_info["result"] = first_result
        await SessionTaskManager.check(second_result)
        return task_info["result"] is first_result
    finally:
        SessionTaskManager._task_list.clear()


async def _test_one_message_completes_only_one_wait_task():
    """同一用户存在多段交互时，一条输入只能推进最早登记的一段。"""
    SessionTaskManager._task_list.clear()
    first = MockMessageSession("first prompt")
    await first.async_init("first prompt")
    second = MockMessageSession("second prompt")
    await second.async_init("second prompt")
    incoming = MockMessageSession("answer")
    await incoming.async_init("answer")
    first_flag = asyncio.Event()
    second_flag = asyncio.Event()
    SessionTaskManager.add_task(first, first_flag, timeout=60)
    SessionTaskManager.add_task(second, second_flag, timeout=60)
    try:
        handled = await SessionTaskManager.check(incoming)
        channel_tasks = SessionTaskManager.get()[first.session_info.target_id][first.session_info.sender_id]
        return (
            handled
            and first_flag.is_set()
            and not second_flag.is_set()
            and channel_tasks[first].get("result") is incoming
            and "result" not in channel_tasks[second]
            and channel_tasks[second]["active"]
        )
    finally:
        SessionTaskManager._task_list.clear()


async def _make_verification_session(response: str, support_button: bool) -> MockMessageSession:
    msg = MockMessageSession(["~test", response], is_ci=True)
    await msg.async_init("~test")
    msg.session_info.support_button = support_button
    return msg


async def _test_verify_user_with_button():
    msg = await _make_verification_session("22", support_button=True)
    with (
        patch("core.builtins.session.internal.Random.sample", return_value=[11, 22, 33]),
        patch("core.builtins.session.internal.Random.choice", return_value=22),
    ):
        result = await msg.verify_user(timeout=30, delete=False)
    return (
        result is True
        and msg.buttons == [{"11": "11", "22": "22", "33": "33"}]
        and any("点击数字“22”" in action for action in msg.action)
    )


async def _test_verify_user_text_fallback():
    msg = await _make_verification_session("22", support_button=False)
    with (
        patch("core.builtins.session.internal.Random.sample", return_value=[11, 22, 33]),
        patch("core.builtins.session.internal.Random.choice", return_value=22),
    ):
        result = await msg.verify_user(timeout=30, delete=False)
    return result is True and not msg.buttons and any("发送数字“22”" in action for action in msg.action)


async def _test_verify_user_rejects_wrong_number():
    msg = await _make_verification_session("33", support_button=True)
    with (
        patch("core.builtins.session.internal.Random.sample", return_value=[11, 22, 33]),
        patch("core.builtins.session.internal.Random.choice", return_value=22),
    ):
        return await msg.verify_user(timeout=30, delete=False) is False


@func_case
async def test_features(tester: Tester):
    """core.builtins.session.features: Features 测试"""
    await tester.test(_test_features_override, "Features.override() 测试")
    await tester.test(_test_features_inject_action_text, "support_action_text 注入测试")
    await tester.test(_test_release_context_tolerates_prior_platform_cleanup, "平台先清理后的上下文释放测试")
    await tester.test(_test_features_inject_markdown_table, "support_markdown_table 注入测试")
    await tester.test(_test_session_refresh_updates_derived_union_state, "SessionInfo 刷新派生状态测试")
    await tester.test(_test_session_refresh_does_not_recreate_deleted_unions, "SessionInfo 刷新不复活已删除 Union")

    return tester


@func_case
async def test_execution_lock(tester: Tester):
    """core.builtins.session.lock: ExecutionLockList 测试"""
    await tester.test(_test_lock_add_remove, "ExecutionLockList 添加和移除测试")
    await tester.test(_test_lock_multiple_users, "ExecutionLockList 多用户锁测试")
    await tester.test(_test_lock_shared_by_bound_identities, "ExecutionLockList 绑定身份共享测试")
    await tester.test(_test_lock_non_owner_cannot_release, "ExecutionLockList 非所有者不能释放测试")
    await tester.test(_test_old_owner_cannot_release_reacquired_lock, "ExecutionLockList 旧所有者幂等释放测试")
    await tester.test(_test_lock_get, "ExecutionLockList.get() 测试")
    await tester.test(_test_lock_detects_union_merge_by_physical_bindings, "Union 合并后物理账号锁冲突测试")
    await tester.test(_test_wait_resume_reacquires_after_competing_command, "等待 continuation 安全重获锁测试")
    await tester.test(_test_cancelled_wait_leaves_no_task_or_lease, "取消等待清理 waiter 与 lease 测试")
    await tester.test(
        _test_execution_lock_state_does_not_survive_session_serialization,
        "SessionInfo 序列化不复制 lease 所有权测试",
    )
    await tester.test(_test_execution_lock_count_counts_leases, "ExecutionLockList 按 lease 计数测试")
    await tester.test(_test_partial_overlap_merge_reservations_do_not_deadlock, "部分重叠 merge reservation 仲裁测试")
    await tester.test(_test_active_sender_leases_are_barriered_before_merge, "活跃 Sender Union 合并 barrier 测试")
    await tester.test(_test_cross_user_wait_result_keeps_root_lock_subject, "跨用户等待结果保持原锁主体测试")
    await tester.test(_test_sleep_waits_for_competing_lease_before_resuming, "sleep continuation 等待重获测试")
    await tester.test(_test_cancelled_sleep_reacquire_keeps_competing_lease, "取消 sleep 重获不破坏竞争 lease")

    return tester


@func_case
async def test_session_task(tester: Tester):
    """core.builtins.session.tasks: SessionTaskManager 测试"""
    await tester.test(_test_task_add_and_get, "SessionTaskManager 添加和获取任务测试")
    await tester.test(_test_task_add_callback, "SessionTaskManager 添加回调测试")
    await tester.test(_test_send_message_binds_button_callback_reply_id, "按钮 callback 虚拟回复 ID 绑定测试")
    await tester.test(_test_button_callback_registered_before_send_returns, "按钮 callback 发送前登记测试")
    await tester.test(_test_send_failure_does_not_leave_callback, "callback 发送失败清理测试")
    await tester.test(_test_virtual_reply_id_triggers_callback, "虚拟 reply_id 复用 callback 匹配测试")
    await tester.test(_test_callback_remains_active_across_aliases, "callback 别名有效期内重复触发测试")
    await tester.test(_test_callback_once_is_consumed_across_aliases, "一次性 callback 别名消费测试")
    await tester.test(_test_reused_callback_keeps_independent_registration, "callback 独立注册互不删除测试")
    await tester.test(_test_shared_callback_fallback_is_not_guessed, "callback 共享 fallback 消歧测试")
    await tester.test(
        _test_callback_registration_handle_survives_alias_collision,
        "callback 相同别名独立注册测试",
    )
    await tester.test(
        _test_pending_plain_callbacks_make_bot_fallback_ambiguous,
        "无按钮 callback 发送前登记与 fallback 消歧测试",
    )
    await tester.test(_test_callback_primary_id_beats_fallback, "callback 主 ID 优先于 fallback 测试")
    await tester.test(_test_callback_ignores_missing_reply_id, "callback 忽略无 reply_id 消息测试")
    await tester.test(_test_callback_is_scoped_by_message_channel, "callback 按消息通道隔离测试")
    await tester.test(_test_callback_finish_is_consumed_as_control_flow, "callback 正常结束控制流测试")
    await tester.test(_test_callback_rejects_other_physical_sender, "callback 物理发送者归属测试")
    await tester.test(_test_callback_ttl_checked_on_use, "callback 即时 TTL 测试")
    await tester.test(_test_repeatable_callback_is_serialized, "可重复 callback 串行执行测试")
    await tester.test(_test_parser_rejects_blocked_wait_responder_before_task_check, "全局屏蔽者不完成等待测试")
    await tester.test(
        _test_parser_rejects_banned_callback_responder_before_task_check, "场景屏蔽者不执行 callback 测试"
    )
    await tester.test(_test_reply_task_normalizes_integer_reply_id, "等待回复 ID 类型归一化测试")
    await tester.test(_test_reply_task_preserves_comma_in_message_id, "等待回复 ID 保留逗号测试")
    await tester.test(_test_wait_task_follows_sender_union_merge, "waiter 跟随 Sender Union 合并测试")
    await tester.test(
        _test_wait_task_follows_sender_unbind_without_old_owner_takeover,
        "waiter 跟随 Sender 解绑并隔离旧账号测试",
    )
    await tester.test(
        _test_wait_task_follows_target_merge_and_current_channel,
        "waiter 跟随 Target 合并与当前通道测试",
    )
    await tester.test(
        _test_wait_task_follows_target_unbind_without_old_channel_takeover,
        "waiter 跟随 Target 解绑并隔离旧场景测试",
    )
    await tester.test(
        _test_wait_task_follows_target_rechannel_without_old_channel_takeover,
        "waiter 跟随场景 rechannel 并隔离旧通道测试",
    )
    await tester.test(
        _test_reply_wait_is_scoped_to_physical_platform_scene,
        "wait_reply 物理平台场景隔离测试",
    )
    await tester.test(
        _test_wait_task_physical_index_survives_refresh_after_topology_change,
        "waiter 拓扑变化后稳定清理索引测试",
    )
    await tester.test(_test_task_bg_check_timeout, "SessionTaskManager.bg_check() 超时处理测试")
    await tester.test(_test_task_remove_prunes_indexes, "SessionTaskManager 完成后释放任务索引测试")
    await tester.test(_test_inactive_task_does_not_capture_message, "SessionTaskManager 已完成任务不覆盖结果测试")
    await tester.test(_test_one_message_completes_only_one_wait_task, "单条输入只完成一个等待任务")
    await tester.test(_test_inactive_wait_releases_context_acquired_during_hold, "失效 waiter 释放已取得 context")
    await tester.test(_test_ready_reply_is_not_blocked_by_earlier_pending_reply, "ready reply 不被 pending 阻塞")
    await tester.test(_test_wait_reply_send_failure_unblocks_pending_parser, "reply 发送失败解除 pending parser")

    return tester


@func_case
async def test_message_session_lifecycle(tester: Tester):
    """core.builtins.session.internal: 消息发送与等待生命周期测试。"""
    await tester.test(_test_send_message_restores_force_markdown_on_failure, "发送失败恢复 Markdown 标志测试")
    await tester.test(_test_wait_next_message_registers_before_fast_reply, "快速回复不丢失测试")
    await tester.test(_test_wait_confirm_registers_before_reaction_roundtrip, "确认反应期间快速回复不丢失测试")
    await tester.test(_test_wait_reply_registers_before_send_returns, "引用回复发送前登记测试")
    await tester.test(_test_wait_reply_timeout_covers_pending_send, "reply 发送阶段受统一超时约束测试")
    await tester.test(_test_wait_reply_timeout_is_single_deadline, "reply 发送与回复共享 deadline 测试")
    await tester.test(_test_wait_reply_none_timeout_keeps_pending_send, "reply 无限超时保留测试")
    await tester.test(
        _test_wait_reply_deletes_prompt_when_reply_registration_is_lost,
        "reply 登记失效后撤回提示测试",
    )
    await tester.test(_test_cancelled_wait_reply_deletes_sent_prompt, "reply 外部取消撤回提示测试")
    await tester.test(
        _test_wait_reply_committed_result_beats_timeout_observation,
        "reply 已提交结果优先于超时观察测试",
    )
    await tester.test(
        _test_wait_reply_delete_failure_does_not_mask_cancellation,
        "reply 撤回失败不覆盖取消测试",
    )
    await tester.test(_test_wait_result_context_release_retries_once, "等待结果 context 释放失败重试测试")
    await tester.test(_test_wait_confirm_can_preserve_merge_barrier, "冲突选择等待保持 merge barrier 测试")
    await tester.test(_test_parser_wait_result_keeps_root_merge_barrier, "真实 parser 保持根 merge barrier 测试")
    return tester


@func_case
async def test_user_verification(tester: Tester):
    """core.builtins.session.internal: 用户操作验证测试"""
    await tester.test(_test_verify_user_with_button, "按钮平台展示三个数字并通过正确答案")
    await tester.test(_test_verify_user_text_fallback, "不支持按钮的平台回退到发送数字")
    await tester.test(_test_verify_user_rejects_wrong_number, "错误数字不能通过验证")

    return tester
