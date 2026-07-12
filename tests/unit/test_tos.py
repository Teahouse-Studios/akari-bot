"""core.tos TOS 管理系统单元测试。"""

import time
from unittest.mock import patch, AsyncMock

from core.tester import func_case, Tester
from core.tester.mock.factory import TestDataFactory
from core.tester.mock.session import MockMessageSession
from core.utils.container import ExpiringTempDict


async def _test_check_temp_ban_no_ban():
    """check_temp_ban: 未封禁时返回 False"""
    try:
        from core.tos import check_temp_ban, temp_ban_counter

        temp_ban_counter.clear()
        result = await check_temp_ban("TEST|nonexistent_target")
        return result is False
    except Exception:
        return False


async def _test_check_temp_ban_with_nested_dict():
    """check_temp_ban: 存储非空 dict 时应返回剩余秒数"""
    try:
        from core.tos import check_temp_ban, temp_ban_counter

        temp_ban_counter.clear()
        target_id = "TEST|ban_target_1"
        ban_entry = ExpiringTempDict(exp=300, ts=time.time())
        ban_entry["active"] = True
        temp_ban_counter[target_id] = ban_entry
        result = await check_temp_ban(target_id)
        temp_ban_counter.clear()
        return isinstance(result, (int, float)) and result > 0
    except Exception:
        return False


async def _test_remove_temp_ban():
    """remove_temp_ban: 应清除封禁记录"""
    try:
        from core.tos import remove_temp_ban, check_temp_ban, temp_ban_counter

        temp_ban_counter.clear()
        target_id = "TEST|ban_target_2"
        ban_entry = ExpiringTempDict(exp=300, ts=time.time())
        ban_entry["active"] = True
        temp_ban_counter[target_id] = ban_entry
        await remove_temp_ban(target_id)
        result = await check_temp_ban(target_id)
        return result is False
    except Exception:
        return False


async def _test_abuse_warn_target_sends_message():
    """abuse_warn_target: 应向用户发送警告消息"""
    try:
        await TestDataFactory.setup_default_test_env()
        msg = MockMessageSession("~test")
        await msg.async_init("~test")
        msg.session_info.sender_info.warns = 0
        msg.session_info.sender_info.trusted = False

        with patch("core.tos.Config") as mock_config:
            mock_config.side_effect = lambda k, *a, **kw: {
                "issue_url": "https://github.com/test/issues",
                "tos_warning_counts": 5,
                "report_targets": [],
            }.get(k, a[0] if a else None)
            with patch("core.tos.tos_report", new_callable=AsyncMock):
                from core.tos import abuse_warn_target

                await abuse_warn_target(msg, "test_reason")

        return len(msg.sent) > 0
    except Exception:
        return False


async def _test_tos_report_no_targets():
    """tos_report: 无报告目标时不报错"""
    try:
        with patch("core.tos.report_targets", []):
            from core.tos import tos_report

            await tos_report("TEST|sender", "TEST|target", "reason")
        return True
    except Exception:
        return False


async def _test_temp_ban_counter_type():
    """temp_ban_counter: 应为 ExpiringTempDict 实例"""
    try:
        from core.tos import temp_ban_counter

        return isinstance(temp_ban_counter, ExpiringTempDict)
    except Exception:
        return False


async def _test_check_temp_ban_expired():
    """check_temp_ban: 过期的封禁应返回 False"""
    try:
        from core.tos import check_temp_ban, temp_ban_counter

        temp_ban_counter.clear()
        target_id = "TEST|ban_expired"
        ban_entry = ExpiringTempDict(exp=0, ts=time.time() - 100)
        ban_entry["active"] = True
        temp_ban_counter[target_id] = ban_entry
        result = await check_temp_ban(target_id)
        temp_ban_counter.clear()
        return result is False
    except Exception:
        return False


@func_case
async def test_tos(tester: Tester):
    """core.tos: TOS 管理系统测试"""
    await tester.test(_test_check_temp_ban_no_ban, "check_temp_ban 未封禁测试")
    await tester.test(_test_check_temp_ban_with_nested_dict, "check_temp_ban 封禁中测试")
    await tester.test(_test_check_temp_ban_expired, "check_temp_ban 过期封禁测试")
    await tester.test(_test_remove_temp_ban, "remove_temp_ban 测试")
    await tester.test(_test_abuse_warn_target_sends_message, "abuse_warn_target 发送消息测试")
    await tester.test(_test_tos_report_no_targets, "tos_report 无目标测试")
    await tester.test(_test_temp_ban_counter_type, "temp_ban_counter 类型测试")
    return tester
