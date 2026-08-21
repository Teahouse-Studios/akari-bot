"""core.retired 单元测试 - 公告文案读取、已发记录与排队。

凡是改动 ``CoreConfig.retired_clients`` 的用例一律放在 ``test_retired_gate.py``：
``tester.py`` 并发执行各个 func_case，而该配置与 ``RETIRED_ROUTES`` 是进程级全局状态，
分散在多个文件中改动会互相覆盖。同一 func_case 内部则是串行的。
"""

import asyncio
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import core.retired as retired_module

from core.database.models import StoredData
from core.retired import (
    NOTIFIED_STORED_KEY,
    RETIRED_NOTIFY_DELAY_MAX,
    RETIRED_NOTIFY_DELAY_MIN,
    has_notified,
    mark_notified,
    pending_notices,
    pick_notice_delay,
    read_notice,
    reset_notified_cache,
    reset_pending_cache,
    should_enqueue_notice,
)
from core.tester import func_case, Tester


def _write(base: Path, client: str, locale: str, text: str):
    """在临时目录中写入一份公告文案。"""
    target = base / client / f"{locale}.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


async def _test_notice_exact_locale():
    """测试公告读取 - 命中当前语言"""
    try:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _write(base, "qq", "zh_cn", "中文公告")
            _write(base, "qq", "en_us", "English notice")
            return read_notice("QQ", "en_us", base) == "English notice"

    except Exception:
        return False


async def _test_notice_falls_back_to_zh_cn():
    """测试公告读取 - 缺少当前语言时回退到 zh_cn"""
    try:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _write(base, "qq", "zh_cn", "中文公告")
            return read_notice("QQ", "ja_jp", base) == "中文公告"

    except Exception:
        return False


async def _test_notice_falls_back_to_any():
    """测试公告读取 - 缺少 zh_cn 时回退到目录内任意文件"""
    try:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _write(base, "qq", "ko_kr", "한국어 공지")
            return read_notice("QQ", "ja_jp", base) == "한국어 공지"

    except Exception:
        return False


async def _test_notice_missing_returns_none():
    """测试公告读取 - 目录缺失时返回 None 交由调用方兜底"""
    try:
        with tempfile.TemporaryDirectory() as tmp:
            return read_notice("QQ", "zh_cn", Path(tmp)) is None

    except Exception:
        return False


async def _test_notified_starts_false():
    """测试已发记录 - 未记录的场景判定为未发送"""
    try:
        await StoredData.filter(stored_key=NOTIFIED_STORED_KEY).delete()
        reset_notified_cache()
        return not await has_notified("QQ|Group|notify1")

    except Exception:
        return False


async def _test_mark_then_notified():
    """测试已发记录 - 记录后判定为已发送"""
    try:
        await StoredData.filter(stored_key=NOTIFIED_STORED_KEY).delete()
        reset_notified_cache()
        await mark_notified("QQ|Group|notify2")
        return await has_notified("QQ|Group|notify2")

    except Exception:
        return False


async def _test_mark_persists_to_storage():
    """测试已发记录 - 记录落库且清空内存后仍可读回"""
    try:
        await StoredData.filter(stored_key=NOTIFIED_STORED_KEY).delete()
        reset_notified_cache()
        await mark_notified("QQ|Group|notify3")

        stored = await StoredData.get_or_none(stored_key=NOTIFIED_STORED_KEY)
        persisted = bool(stored) and any(r.get("target_id") == "QQ|Group|notify3" for r in stored.value)

        # 清空内存后重新加载，验证 list 与 dict 的互转无损。
        reset_notified_cache()
        return persisted and await has_notified("QQ|Group|notify3")

    except Exception:
        return False


async def _test_mark_keeps_existing_records():
    """测试已发记录 - 追加记录不会覆盖既有条目"""
    try:
        await StoredData.filter(stored_key=NOTIFIED_STORED_KEY).delete()
        reset_notified_cache()
        await mark_notified("QQ|Group|keep1")
        await mark_notified("QQ|Group|keep2")
        reset_notified_cache()
        return await has_notified("QQ|Group|keep1") and await has_notified("QQ|Group|keep2")

    except Exception:
        return False


async def _test_delay_within_range():
    """测试公告排队 - 随机延迟落在配置区间内"""
    try:
        # 取多次以降低偶然通过的可能，随机源已由测试框架接管。
        return all(RETIRED_NOTIFY_DELAY_MIN <= pick_notice_delay() <= RETIRED_NOTIFY_DELAY_MAX for _ in range(20))

    except Exception:
        return False


async def _test_enqueue_skips_notified():
    """测试公告排队 - 已发送过的场景不再排队"""
    try:
        await StoredData.filter(stored_key=NOTIFIED_STORED_KEY).delete()
        reset_notified_cache()
        reset_pending_cache()
        await mark_notified("QQ|Group|queued1")
        return not await should_enqueue_notice("QQ|Group|queued1")

    except Exception:
        return False


async def _test_enqueue_skips_pending():
    """测试公告排队 - 已在队列中的场景不重复排队"""
    try:
        await StoredData.filter(stored_key=NOTIFIED_STORED_KEY).delete()
        reset_notified_cache()
        reset_pending_cache()

        first = await should_enqueue_notice("QQ|Group|queued2")
        pending_notices.add("QQ|Group|queued2")
        second = await should_enqueue_notice("QQ|Group|queued2")
        reset_pending_cache()
        return first and not second

    except Exception:
        return False


async def _test_enqueue_allows_fresh_target():
    """测试公告排队 - 未发送且未排队的场景允许排队"""
    try:
        await StoredData.filter(stored_key=NOTIFIED_STORED_KEY).delete()
        reset_notified_cache()
        reset_pending_cache()
        return await should_enqueue_notice("QQ|Group|queued3")

    except Exception:
        return False


async def _test_concurrent_marks_do_not_persist_stale_snapshot():
    """测试已发记录 - 并发慢写不能用旧快照覆盖较新的完整记录。"""
    persisted = []
    created = 0
    previous_notified = retired_module._notified

    class FakeStored:
        def __init__(self, delay: float):
            self.delay = delay
            self.value = []

        async def save(self):
            snapshot = list(self.value)
            await asyncio.sleep(self.delay)
            persisted[:] = snapshot

    async def get_or_create(**_kwargs):
        nonlocal created
        created += 1
        # 未串行化时，第一笔保存会在第二笔之后完成，并以只含第一个场景的旧快照覆盖数据库。
        return FakeStored(0.02 if created == 1 else 0), created == 1

    retired_module._notified = {}
    try:
        with patch.object(retired_module.StoredData, "get_or_create", new=get_or_create):
            first = asyncio.create_task(mark_notified("QQ|Group|concurrent-mark-1"))
            await asyncio.sleep(0)
            second = asyncio.create_task(mark_notified("QQ|Group|concurrent-mark-2"))
            await asyncio.gather(first, second)
        return {record["target_id"] for record in persisted} == {
            "QQ|Group|concurrent-mark-1",
            "QQ|Group|concurrent-mark-2",
        }
    finally:
        retired_module._notified = previous_notified


async def _test_failed_mark_rolls_back_memory_state():
    """测试已发记录 - 落库失败不把内存永久标成已发送。"""
    target_id = "QQ|Group|failed-mark"
    previous_notified = retired_module._notified

    class FakeStored:
        value = []

        async def save(self):
            raise RuntimeError("save failed")

    async def get_or_create(**_kwargs):
        return FakeStored(), True

    retired_module._notified = {}
    try:
        with patch.object(retired_module.StoredData, "get_or_create", new=get_or_create):
            try:
                await mark_notified(target_id)
            except RuntimeError:
                return target_id not in retired_module._notified and await should_enqueue_notice(target_id)
        return False
    finally:
        retired_module._notified = previous_notified


async def _test_enqueue_concurrent_same_target_once():
    """测试公告排队 - 同一新场景并发触发只创建一个投递任务。"""
    target_id = "QQ|Group|queued-concurrent"
    await StoredData.filter(stored_key=NOTIFIED_STORED_KEY).delete()
    reset_notified_cache()
    reset_pending_cache()

    delivered = []
    original_deliver = retired_module._deliver_notice
    original_pick_delay = retired_module.pick_notice_delay

    async def fake_deliver(session_info, delay: int):
        delivered.append((session_info.target_id, delay))

    retired_module._deliver_notice = fake_deliver
    retired_module.pick_notice_delay = lambda: 0
    try:
        session_info = SimpleNamespace(target_id=target_id)
        results = await asyncio.gather(
            retired_module.enqueue_notice(session_info),
            retired_module.enqueue_notice(session_info),
        )
        # enqueue_notice 只负责创建后台任务，显式让出一次事件循环使替身完成。
        await asyncio.sleep(0)
        return results.count(True) == 1 and delivered == [(target_id, 0)]
    finally:
        retired_module._deliver_notice = original_deliver
        retired_module.pick_notice_delay = original_pick_delay
        reset_pending_cache()


async def _test_notice_cleanup_cancels_retained_delivery():
    """测试公告排队 - 生命周期清理取消延时任务并释放 pending 占位。"""
    target_id = "QQ|Group|cancelled-notice"
    previous_notified = retired_module._notified
    original_pick_delay = retired_module.pick_notice_delay
    retired_module._notified = {}
    reset_pending_cache()
    retired_module.pick_notice_delay = lambda: 3600
    try:
        queued = await retired_module.enqueue_notice(SimpleNamespace(target_id=target_id))
        retained = bool(retired_module._notice_tasks) and target_id in pending_notices
        await retired_module.cancel_retired_notice_tasks()
        await asyncio.sleep(0)
        return queued and retained and target_id not in pending_notices and not retired_module._notice_tasks
    finally:
        retired_module.pick_notice_delay = original_pick_delay
        retired_module._notified = previous_notified
        await retired_module.cancel_retired_notice_tasks()
        reset_pending_cache()


@func_case
async def test_retired_notice(tester: Tester):
    """core.retired: 公告读取、已发记录与排队测试"""
    await tester.test(_test_notice_exact_locale, "命中当前语言测试")
    await tester.test(_test_notice_falls_back_to_zh_cn, "回退 zh_cn 测试")
    await tester.test(_test_notice_falls_back_to_any, "回退任意文件测试")
    await tester.test(_test_notice_missing_returns_none, "文案缺失兜底测试")
    await tester.test(_test_notified_starts_false, "未记录判定测试")
    await tester.test(_test_mark_then_notified, "记录后判定测试")
    await tester.test(_test_mark_persists_to_storage, "记录落库测试")
    await tester.test(_test_mark_keeps_existing_records, "追加不覆盖测试")
    await tester.test(_test_concurrent_marks_do_not_persist_stale_snapshot, "并发记录不回写旧快照测试")
    await tester.test(_test_failed_mark_rolls_back_memory_state, "落库失败回滚内存记录测试")
    await tester.test(_test_delay_within_range, "随机延迟区间测试")
    await tester.test(_test_enqueue_skips_notified, "已发送不排队测试")
    await tester.test(_test_enqueue_skips_pending, "已排队不重复测试")
    await tester.test(_test_enqueue_allows_fresh_target, "新场景允许排队测试")
    await tester.test(_test_enqueue_concurrent_same_target_once, "同场景并发只排队一次测试")
    await tester.test(_test_notice_cleanup_cancels_retained_delivery, "公告后台清理测试")

    return tester
