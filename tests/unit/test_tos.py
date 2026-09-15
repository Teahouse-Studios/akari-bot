"""core.utils.tos TOS 管理系统单元测试。"""

import time
from unittest.mock import patch, AsyncMock

from core.builtins.session.info import SessionInfo
from core.constants import AbuseWarning, SessionFinished
from core.database.models import SenderUnionInfo
from core.tester import func_case, Tester
from core.tester.mock.factory import TestDataFactory
from core.tester.mock.session import MockMessageSession
from core.utils.container import ExpiringTempDict


async def _test_check_temp_ban_no_ban():
    """check_temp_ban: 未封禁时返回 False"""
    try:
        from core.utils.tos import check_temp_ban, temp_ban_counter

        temp_ban_counter.clear()
        result = await check_temp_ban("TEST|nonexistent_target")
        return result is False
    except Exception:
        return False


async def _test_check_temp_ban_with_nested_dict():
    """check_temp_ban: 存储非空 dict 时应返回剩余秒数"""
    try:
        from core.utils.tos import check_temp_ban, temp_ban_counter

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
        from core.utils.tos import remove_temp_ban, check_temp_ban, temp_ban_counter

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
    await TestDataFactory.setup_default_test_env()
    msg = MockMessageSession("~test")
    await msg.async_init("~test")
    msg.session_info.sender_union_info.warns = 0
    msg.session_info.sender_union_info.trusted = False

    class MockConfig:
        """替换 CoreConfig 的桩。tos_warning_counts 与 report_targets 在导入时即已取值，
        此处仅提供 abuse_warn_target 内部实时读取的字段。"""

        issue_url = "https://github.com/test/issues"

    # 默认测试环境将发送者置为超级用户，而 abuse_warn_target 对超级用户直接跳过警告，
    # 若不覆写该判定，本用例断言的发送行为永远不会发生。
    with (
        patch.object(MockMessageSession, "check_super_user", lambda self: False),
        patch("core.utils.tos.CoreConfig", MockConfig),
        patch("core.utils.tos.tos_report", new_callable=AsyncMock),
    ):
        from core.utils.tos import abuse_warn_target

        await abuse_warn_target(msg, "test_reason")

    return len(msg.sent) > 0


async def _test_tos_report_no_targets():
    """tos_report: 无报告场景时不报错"""
    try:
        with patch("core.utils.tos.report_targets", []):
            from core.utils.tos import tos_report

            await tos_report("TEST|sender", "TEST|target", "reason")
        return True
    except Exception:
        return False


async def _test_temp_ban_counter_type():
    """temp_ban_counter: 应为 ExpiringTempDict 实例"""
    try:
        from core.utils.tos import temp_ban_counter

        return isinstance(temp_ban_counter, ExpiringTempDict)
    except Exception:
        return False


async def _test_check_temp_ban_expired():
    """check_temp_ban: 过期的封禁应返回 False"""
    try:
        from core.utils.tos import check_temp_ban, temp_ban_counter

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


async def _bound_sessions(prefix: str):
    first_id = f"TEST|{prefix}|1"
    second_id = f"TEST|{prefix}|2"
    union = await SenderUnionInfo.resolve_union(first_id)
    await union.bind_id(second_id)

    async def make(sender_id: str):
        msg = MockMessageSession("~test")
        msg.session_info = await SessionInfo.assign(
            target_id=f"TEST|Group|{prefix}",
            target_from="TEST|Group",
            client_name="TEST",
            sender_id=sender_id,
            sender_from="TEST",
        )
        return msg

    return await make(first_id), await make(second_id)


async def _test_temp_ban_shared_by_sender_union():
    """临时封禁不能通过切换同一 Union 下的另一个平台身份绕过。"""
    from core.builtins.parser.message import _tos_temp_ban
    from core.utils.tos import temp_ban_counter

    first, second = await _bound_sessions("temp-ban-union")
    temp_ban_counter.clear()
    entry = ExpiringTempDict(exp=300, ts=time.time(), root=False)
    entry["count"] = 0
    temp_ban_counter[first.session_info.sender_union_id] = entry
    try:
        try:
            await _tos_temp_ban(second)
        except SessionFinished:
            return True
        return False
    finally:
        temp_ban_counter.clear()


async def _test_rate_bucket_shared_by_sender_union():
    """单命令令牌桶应由绑定身份共同消耗。"""
    from core.builtins.parser.message import _tos_msg_counter, buckets_all, buckets_same

    first, second = await _bound_sessions("rate-union")
    buckets_same.clear()
    buckets_all.clear()
    try:
        for index in range(10):
            await _tos_msg_counter(first if index % 2 == 0 else second, "same-command")
        try:
            await _tos_msg_counter(second, "same-command")
        except AbuseWarning:
            return True
        return False
    finally:
        buckets_same.clear()
        buckets_all.clear()


@func_case
async def test_tos(tester: Tester):
    """core.utils.tos: TOS 管理系统测试"""
    await tester.test(_test_check_temp_ban_no_ban, "check_temp_ban 未封禁测试")
    await tester.test(_test_check_temp_ban_with_nested_dict, "check_temp_ban 封禁中测试")
    await tester.test(_test_check_temp_ban_expired, "check_temp_ban 过期封禁测试")
    await tester.test(_test_remove_temp_ban, "remove_temp_ban 测试")
    await tester.test(_test_abuse_warn_target_sends_message, "abuse_warn_target 发送消息测试")
    await tester.test(_test_tos_report_no_targets, "tos_report 无场景测试")
    await tester.test(_test_temp_ban_counter_type, "temp_ban_counter 类型测试")
    await tester.test(_test_temp_ban_shared_by_sender_union, "临时封禁按用户 Union 共享测试")
    await tester.test(_test_rate_bucket_shared_by_sender_union, "ToS 令牌桶按用户 Union 共享测试")
    return tester
