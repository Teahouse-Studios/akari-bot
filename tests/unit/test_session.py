"""core.builtins.session 会话系统单元测试。"""

import asyncio

from core.builtins.session.features import Features
from core.builtins.session.lock import ExecutionLockList
from core.builtins.session.tasks import SessionTaskManager
from core.tester import func_case, Tester
from core.tester.mock.session import MockMessageSession


def _test_features_default():
    """测试 Features 默认值"""
    try:
        features = Features()
        if features.support_image is not False:
            return False
        if features.support_voice is not False:
            return False
        if features.support_mention is not False:
            return False
        if features.support_embed is not False:
            return False
        if features.support_forward is not False:
            return False
        if features.support_delete is not False:
            return False
        if features.support_manage is not False:
            return False
        if features.support_markdown is not False:
            return False
        if features.support_reaction is not False:
            return False
        if features.support_quote is not False:
            return False
        if features.support_rss is not False:
            return False
        if features.support_typing is not False:
            return False
        if features.support_wait is not False:
            return False
        return True
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

        if "TEST|Console|0" not in task_list:
            return False
        if "TEST|0" not in task_list["TEST|Console|0"]:
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
        task_info = task_list["TEST|Console|0"]["TEST|0"][msg]
        if task_info["active"]:
            return False

        if not flag.is_set():
            return False

        SessionTaskManager._task_list.clear()

        return True
    except Exception:
        return False


@func_case
async def test_features(tester: Tester):
    """core.builtins.session.features: Features 测试"""
    await tester.test(_test_features_default, "Features 默认值测试")
    await tester.test(_test_features_override, "Features.override() 测试")

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

    return tester
