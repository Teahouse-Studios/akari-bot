"""ToS 管理系统单元测试（实现位于 modules/core/hooks/tos.py）。"""

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from core.builtins.session.info import SessionInfo
from core.constants.exceptions import SendMessageFailed, SessionFinished, WaitCancelException
from core.database.models import SenderUnionInfo
from core.tester import Tester, func_case
from core.tester.timing import TIME_SCALE
from core.tester.mock.factory import TestDataFactory
from core.tester.mock.session import MockMessageSession
from core.utils.container import ExpiringTempDict


async def _test_check_temp_ban_no_ban():
    try:
        from modules.core.hooks.tos import check_temp_ban, temp_ban_counter

        temp_ban_counter.clear()
        result = await check_temp_ban("TEST|nonexistent_target")
        return result is False
    except Exception:
        return False


async def _test_check_temp_ban_with_nested_dict():
    try:
        from modules.core.hooks.tos import check_temp_ban, temp_ban_counter

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
    try:
        from modules.core.hooks.tos import check_temp_ban, remove_temp_ban, temp_ban_counter

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
    await TestDataFactory.setup_default_test_env()
    msg = MockMessageSession("~test")
    await msg.async_init("~test")
    msg.session_info.sender_union_info.warns = 0
    msg.session_info.sender_union_info.trusted = False

    class MockConfig:
        issue_url = "https://github.com/test/issues"

    with (
        patch.object(MockMessageSession, "check_super_user", lambda self: False),
        patch("modules.core.hooks.tos.CoreConfig", MockConfig),
        patch("modules.core.hooks.tos.tos_report", new_callable=AsyncMock),
        patch("modules.core.hooks.tos._warning_counts", return_value=1),
    ):
        from modules.core.hooks.tos import abuse_warn_target

        await abuse_warn_target(msg, "test_reason")

    return len(msg.sent) > 0


async def _test_tos_report_no_targets():
    try:
        from modules.core.hooks.tos import tos_report

        with patch("modules.core.hooks.tos._report_targets", return_value=[]):
            await tos_report("TEST|sender", "TEST|target", "reason")
        return True
    except Exception:
        return False


async def _test_tos_report_delegates_to_send_report():
    from core.builtins.message.chain import MessageChain
    from core.builtins.message.elements import I18NContextElement
    from modules.core.hooks.tos import tos_report

    with (
        patch("modules.core.hooks.tos._report_targets", return_value=["TEST|Group|report"]),
        patch("modules.core.hooks.tos.send_report", new_callable=AsyncMock) as report,
    ):
        await tos_report("TEST|sender", "TEST|target", "{I18N:tos.message.reason.abuse}")

    message = report.await_args.args[0]
    elements = [element for element in message.values if isinstance(element, I18NContextElement)]
    action = next(element for element in elements if element.key == "tos.message.action")
    return (
        isinstance(message, MessageChain)
        and [element.key for element in elements] == ["tos.message.report", "tos.message.reason", "tos.message.action"]
        and action.kwargs["action"] == "{I18N:tos.message.action.warning}"
        and report.await_args.kwargs["targets"] == ["TEST|Group|report"]
        and "TEST|sender" in report.await_args.kwargs["subject"]
    )


async def _test_tos_report_blocked_action():
    from core.builtins.message.elements import I18NContextElement
    from modules.core.hooks.tos import tos_report

    with patch("modules.core.hooks.tos.send_report", new_callable=AsyncMock) as report:
        await tos_report("TEST|sender", "TEST|target", "{I18N:tos.message.reason.abuse}", banned=True)

    message = report.await_args.args[0]
    action = next(
        element
        for element in message.values
        if isinstance(element, I18NContextElement) and element.key == "tos.message.action"
    )
    return action.kwargs["action"] == "{I18N:tos.message.action.blocked}"


async def _test_tos_report_email_takes_priority():
    from core.builtins.bot import Bot
    from core.config.base import SMTPConfig
    from modules.core.hooks.tos import tos_report

    direct_sender = AsyncMock()
    with (
        patch.object(SMTPConfig, "enable_email_report", True),
        patch.object(SMTPConfig, "smtp_host", "smtp.example.com"),
        patch.object(SMTPConfig, "smtp_recipients", ["ops@example.com"]),
        patch("core.smtp.send_email") as send_email,
        patch.object(Bot, "send_direct_message", direct_sender),
        patch("modules.core.hooks.tos._report_targets", return_value=["TEST|Group|report"]),
    ):
        await tos_report("TEST|sender", "TEST|target", "{I18N:tos.message.reason.abuse}", banned=True)

    subject, body = send_email.call_args.args
    return (
        send_email.call_count == 1 and "TEST|sender" in subject and "TEST|target" in body and not direct_sender.called
    )


async def _test_temp_ban_counter_type():
    try:
        from modules.core.hooks.tos import temp_ban_counter

        return isinstance(temp_ban_counter, ExpiringTempDict)
    except Exception:
        return False


async def _test_check_temp_ban_expired():
    try:
        from modules.core.hooks.tos import check_temp_ban, temp_ban_counter

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
    from core.builtins.parser.hooks import Stop
    from modules.core.hooks.tos import _temp_ban_check, temp_ban_counter

    first, second = await _bound_sessions("temp-ban-union")
    temp_ban_counter.clear()
    entry = ExpiringTempDict(exp=300, ts=time.time(), root=False)
    entry["count"] = 0
    temp_ban_counter[first.session_info.sender_union_id] = entry
    try:
        result = await _temp_ban_check(second)
        return isinstance(result, Stop)
    finally:
        temp_ban_counter.clear()


async def _test_rate_bucket_shared_by_sender_union():
    from core.builtins.parser.hooks import Stop
    from modules.core.hooks.tos import _buckets_all, _buckets_same, _msg_counter

    first, second = await _bound_sessions("rate-union")
    _buckets_same.clear()
    _buckets_all.clear()
    try:
        for index in range(10):
            result = await _msg_counter(first if index % 2 == 0 else second, "same-command")
            assert result is None
        result = await _msg_counter(second, "same-command")
        return isinstance(result, Stop)
    finally:
        _buckets_same.clear()
        _buckets_all.clear()


@func_case
async def test_tos(tester: Tester):
    """modules.core.hooks.tos: TOS 管理系统测试"""
    await tester.test(_test_check_temp_ban_no_ban, "check_temp_ban 未封禁测试")
    await tester.test(_test_check_temp_ban_with_nested_dict, "check_temp_ban 封禁中测试")
    await tester.test(_test_check_temp_ban_expired, "check_temp_ban 过期封禁测试")
    await tester.test(_test_remove_temp_ban, "remove_temp_ban 测试")
    await tester.test(_test_abuse_warn_target_sends_message, "abuse_warn_target 发送消息测试")
    await tester.test(_test_tos_report_no_targets, "tos_report 无场景测试")
    await tester.test(_test_tos_report_delegates_to_send_report, "tos_report 经上报服务分发测试")
    await tester.test(_test_tos_report_blocked_action, "tos_report 封禁动作测试")
    await tester.test(_test_tos_report_email_takes_priority, "tos_report 邮件上报优先测试")
    await tester.test(_test_temp_ban_counter_type, "temp_ban_counter 类型测试")
    await tester.test(_test_temp_ban_shared_by_sender_union, "临时封禁按用户 Union 共享测试")
    await tester.test(_test_rate_bucket_shared_by_sender_union, "ToS 令牌桶按用户 Union 共享测试")
    await tester.test(_test_counter_overflow_survives_notify_failure, "超限拒绝不被通知故障丢弃测试")
    await tester.test(_test_temp_ban_hint_has_no_compat_metadata, "临封提示不携带兼容元数据测试")
    await tester.test(_test_penalty_cancellation_propagates, "ToS 通知保留取消与进程退出信号测试")
    await tester.test(_test_enforcement_failure_stops_execution, "ToS 检查故障拒绝执行并保留退出信号测试")
    await tester.test(_test_slow_penalty_keeps_rejection, "ToS 处罚不受默认 hook 超时策略放行测试")
    return tester


async def _dispatch_tos_point(point, msg):
    from core.builtins.parser.hooks import ParserHookExecutor, build_subscription
    from core.loader import ModulesManager

    module = ModulesManager.modules["tos"]
    subscriptions = [
        build_subscription("tos", meta, index)
        for index, meta in enumerate(module.hooks_list.set)
        if meta.point == point
    ]
    assert subscriptions
    manager = SimpleNamespace(modules={"tos": module}, parser_hook_subscriptions={point: subscriptions})
    return await ParserHookExecutor(manager).dispatch(
        point, msg, module_name="__tos_probe", data={"show_typing": True, "base": False}
    )


async def _test_counter_overflow_survives_notify_failure():
    from core.builtins.parser.hooks import HookPoint, Stop, StopScope
    from modules.core.hooks.tos import _buckets_all, _buckets_same, _msg_counter

    first, _ = await _bound_sessions("notify-fail-union")
    first.trigger_msg = "flood-command"
    _buckets_same.clear()
    _buckets_all.clear()
    try:
        with patch("modules.core.hooks.tos._enable_tos", return_value=True):
            for _ in range(10):
                assert await _msg_counter(first, first.trigger_msg) is None
            for point, scope in (
                (HookPoint.COMMAND_BEFORE_PARSE, StopScope.MESSAGE),
                (HookPoint.REGEX_BEFORE_EXECUTE, StopScope.CANDIDATE),
            ):
                for error in (
                    RuntimeError("report down"),
                    SendMessageFailed(),
                    SessionFinished(),
                    WaitCancelException(),
                ):
                    with patch("modules.core.hooks.tos._apply_abuse", new=AsyncMock(side_effect=error)):
                        outcome = await _dispatch_tos_point(point, first)
                    assert outcome.failed == 0 and outcome.executed == 1
                    assert isinstance(outcome.result, Stop) and outcome.result.scope == scope
        return True
    finally:
        _buckets_same.clear()
        _buckets_all.clear()


async def _test_temp_ban_hint_has_no_compat_metadata():
    from core.builtins.parser.hooks import HookPoint, Stop
    from modules.core.hooks.tos import _temp_ban_check, temp_ban_counter

    first, _ = await _bound_sessions("stats-compat-union")
    temp_ban_counter.clear()
    try:
        # 两种提示都必须通过真实 executor 的消息类型校验，不能降级为 Continue。
        with patch("modules.core.hooks.tos._enable_tos", return_value=True):
            for point in (HookPoint.COMMAND_PREPARE, HookPoint.REGEX_PREPARE):
                for count in (0, 2):
                    entry = ExpiringTempDict(exp=300, ts=time.time(), root=False)
                    entry["count"] = count
                    temp_ban_counter[first.session_info.sender_union_id] = entry
                    outcome = await _dispatch_tos_point(point, first)
                    assert outcome.failed == 0 and outcome.executed == 1
                    hint = outcome.result
                    assert isinstance(hint, Stop)
                    assert "stats_compat" not in hint.data
                    assert not hint.data.get("penalty")

        # count=4 → 升级处罚分支，标记为 penalty 且无兼容统计标记
        temp_ban_counter.clear()
        entry2 = ExpiringTempDict(exp=300, ts=time.time(), root=False)
        entry2["count"] = 4
        temp_ban_counter[first.session_info.sender_union_id] = entry2
        with patch("modules.core.hooks.tos._apply_abuse", new=AsyncMock()):
            escalated = await _temp_ban_check(first)
        assert isinstance(escalated, Stop)
        assert escalated.data.get("penalty")
        assert "stats_compat" not in escalated.data
        return True
    finally:
        temp_ban_counter.clear()


async def _test_penalty_cancellation_propagates():
    from modules.core.hooks.tos import _apply_abuse_safely

    for error in (asyncio.CancelledError(), SystemExit(), KeyboardInterrupt()):
        with patch("modules.core.hooks.tos._apply_abuse", new=AsyncMock(side_effect=error)):
            try:
                await _apply_abuse_safely(None, "reason")
            except BaseException as raised:
                assert raised is error
            else:
                return False
    return True


async def _test_enforcement_failure_stops_execution():
    from core.builtins.parser.hooks import HookPoint, Stop, StopScope

    first, _ = await _bound_sessions("check-fail-union")
    for point in (
        HookPoint.COMMAND_PREPARE,
        HookPoint.COMMAND_BEFORE_PARSE,
        HookPoint.REGEX_PREPARE,
        HookPoint.REGEX_BEFORE_EXECUTE,
    ):
        with patch("modules.core.hooks.tos._enable_tos", side_effect=RuntimeError("check failed")):
            outcome = await _dispatch_tos_point(point, first)
        assert outcome.failed == 0 and outcome.executed == 1
        assert isinstance(outcome.result, Stop) and outcome.result.scope == StopScope.MESSAGE
        assert outcome.result.data["error"] == "tos_check_failed"
        for error in (asyncio.CancelledError(), SystemExit(), KeyboardInterrupt()):
            with patch("modules.core.hooks.tos._enable_tos", side_effect=error):
                try:
                    await _dispatch_tos_point(point, first)
                except BaseException as raised:
                    assert raised is error
                else:
                    return False
    return True


async def _test_slow_penalty_keeps_rejection():
    from core.builtins.parser.hooks import HookPoint, Stop
    from core.loader import ModulesManager
    from modules.core.hooks.tos import _buckets_all, _buckets_same, _msg_counter

    enforced_points = {
        HookPoint.COMMAND_PREPARE,
        HookPoint.COMMAND_BEFORE_PARSE,
        HookPoint.REGEX_PREPARE,
        HookPoint.REGEX_BEFORE_EXECUTE,
    }
    metas = [meta for meta in ModulesManager.modules["tos"].hooks_list.set if meta.point in enforced_points]
    assert len(metas) == len(enforced_points) and all(meta.timeout == 0 for meta in metas)

    async def slow_penalty(*_args):
        await asyncio.sleep(0.02)

    first, _ = await _bound_sessions("slow-penalty-union")
    first.trigger_msg = "slow-flood"
    _buckets_same.clear()
    _buckets_all.clear()
    try:
        with patch("modules.core.hooks.tos._enable_tos", return_value=True):
            for _ in range(10):
                assert await _msg_counter(first, first.trigger_msg) is None
            with patch("modules.core.hooks.tos._apply_abuse", side_effect=slow_penalty):
                outcome = await asyncio.wait_for(
                    _dispatch_tos_point(HookPoint.COMMAND_BEFORE_PARSE, first),
                    timeout=0.5 * TIME_SCALE,
                )
        assert outcome.failed == 0 and outcome.executed == 1
        return isinstance(outcome.result, Stop)
    finally:
        _buckets_same.clear()
        _buckets_all.clear()
