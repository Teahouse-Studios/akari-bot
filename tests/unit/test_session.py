"""core.builtins.session 会话系统单元测试。"""

import asyncio
from unittest.mock import patch

from core.builtins.session.features import Features
from core.builtins.session.lock import ExecutionLockList
from core.builtins.session.tasks import SessionTaskManager
from core.tester import func_case, Tester
from core.tester.mock.session import MockMessageSession


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


async def _test_lock_get():
    """测试 ExecutionLockList.get()"""
    try:
        msg = MockMessageSession("~test")
        await msg.async_init("~test")

        ExecutionLockList.add(msg)
        lock_set = ExecutionLockList.get()
        if not isinstance(lock_set, set):
            return False
        if "TEST|0" not in lock_set:
            return False

        ExecutionLockList.remove(msg)

        return True
    except Exception:
        return False


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

        # 任务按消息通道建键：同一现实场景下的多个平台场景共用一份等待任务，
        # 用户在哪个平台回复都能命中；仅共享 union 而通道号不同的场景则各管各的。
        if session_info.channel_key not in task_list:
            return False
        if session_info.sender_union_id not in task_list[session_info.channel_key]:
            return False
        if session_info.target_id in task_list or session_info.target_union_id in task_list:
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

        SessionTaskManager.add_callback("12345", test_callback)
        if "12345" not in SessionTaskManager._callback_list:
            return False

        del SessionTaskManager._callback_list["12345"]

        return True
    except Exception:
        return False


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
        task_info = task_list[session_info.channel_key][session_info.sender_union_id][msg]
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
        task_info = SessionTaskManager.get()[waiting.session_info.channel_key][waiting.session_info.sender_union_id][
            waiting
        ]
        task_info["active"] = False
        task_info["result"] = first_result
        await SessionTaskManager.check(second_result)
        return task_info["result"] is first_result
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
    await tester.test(_test_features_inject_markdown_table, "support_markdown_table 注入测试")

    return tester


@func_case
async def test_execution_lock(tester: Tester):
    """core.builtins.session.lock: ExecutionLockList 测试"""
    await tester.test(_test_lock_add_remove, "ExecutionLockList 添加和移除测试")
    await tester.test(_test_lock_multiple_users, "ExecutionLockList 多用户锁测试")
    await tester.test(_test_lock_get, "ExecutionLockList.get() 测试")

    return tester


@func_case
async def test_session_task(tester: Tester):
    """core.builtins.session.tasks: SessionTaskManager 测试"""
    await tester.test(_test_task_add_and_get, "SessionTaskManager 添加和获取任务测试")
    await tester.test(_test_task_add_callback, "SessionTaskManager 添加回调测试")
    await tester.test(_test_task_bg_check_timeout, "SessionTaskManager.bg_check() 超时处理测试")
    await tester.test(_test_task_remove_prunes_indexes, "SessionTaskManager 完成后释放任务索引测试")
    await tester.test(_test_inactive_task_does_not_capture_message, "SessionTaskManager 已完成任务不覆盖结果测试")

    return tester


@func_case
async def test_user_verification(tester: Tester):
    """core.builtins.session.internal: 用户操作验证测试"""
    await tester.test(_test_verify_user_with_button, "按钮平台展示三个数字并通过正确答案")
    await tester.test(_test_verify_user_text_fallback, "不支持按钮的平台回退到发送数字")
    await tester.test(_test_verify_user_rejects_wrong_number, "错误数字不能通过验证")

    return tester
