"""core.retired 单元测试 - 公告文案读取、已发记录与排队。

凡是改动 ``CoreConfig.retired_clients`` 的用例一律放在 ``test_retired_gate.py``：
``tester.py`` 并发执行各个 func_case，而该配置与 ``RETIRED_ROUTES`` 是进程级全局状态，
分散在多个文件中改动会互相覆盖。同一 func_case 内部则是串行的。
"""

import tempfile
from pathlib import Path

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
    await tester.test(_test_delay_within_range, "随机延迟区间测试")
    await tester.test(_test_enqueue_skips_notified, "已发送不排队测试")
    await tester.test(_test_enqueue_skips_pending, "已排队不重复测试")
    await tester.test(_test_enqueue_allows_fresh_target, "新场景允许排队测试")

    return tester
