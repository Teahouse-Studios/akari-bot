"""QQBot 会话上下文回收后 reaction 与错误信号的容错测试。"""

from bots.qqbot.context import QQBotContextManager
from bots.qqbot.info import target_guild_prefix, target_group_prefix
from core.builtins.session.info import SessionInfo
from core.constants import SessionContextUnavailable
from core.tester import Tester, func_case


def _make_session(session_id: str, target_from: str = target_group_prefix, message_id: str = "m1") -> SessionInfo:
    return SessionInfo(
        target_id=f"{target_from}|test_target",
        sender_id="QQ|Tiny|1",
        target_from=target_from,
        client_name="QQBot",
        session_id=session_id,
        message_id=message_id,
    )


class _FailingAPI:
    def __init__(self):
        self.calls = 0

    async def put_reaction(self, **kwargs):
        self.calls += 1
        raise RuntimeError("platform rejected the reaction")

    async def delete_reaction(self, **kwargs):
        self.calls += 1
        raise RuntimeError("platform rejected the reaction")


class _Client:
    def __init__(self):
        self.api = _FailingAPI()


class _ClientScope:
    """替换 QQBotContextManager.client，避免测试依赖真实 botpy 客户端。"""

    def __init__(self, client=None):
        self.client = client

    def __enter__(self):
        self._origin = QQBotContextManager.__dict__.get("client")
        QQBotContextManager.client = self.client
        return self

    def __exit__(self, *exc_info):
        QQBotContextManager.client = self._origin
        return False


async def _test_error_signal_skips_when_context_dropped() -> bool:
    session = _make_session("error-signal-context-dropped")
    QQBotContextManager.context.pop(session.session_id, None)
    # 回包时上下文已被 del_context 回收，此处不应再抛异常，否则会中断 RPC 管道。
    with _ClientScope(None):
        try:
            await QQBotContextManager.error_signal(session)
        except Exception:
            return False
    return True


async def _test_error_signal_swallows_api_failure() -> bool:
    session = _make_session("error-signal-api-failure", target_from=target_guild_prefix)
    QQBotContextManager.context[session.session_id] = object()
    client = _Client()
    try:
        with _ClientScope(client):
            try:
                await QQBotContextManager.error_signal(session)
            except Exception:
                return False
        return client.api.calls == 1
    finally:
        QQBotContextManager.context.pop(session.session_id, None)


async def _test_add_reaction_skips_when_context_dropped() -> bool:
    session = _make_session("add-reaction-context-dropped", target_from=target_guild_prefix)
    QQBotContextManager.context.pop(session.session_id, None)
    with _ClientScope(None):
        try:
            await QQBotContextManager.add_reaction(session, ["m1"], "1")
        except Exception:
            return False
    return True


async def _test_error_signal_ignores_non_guild_targets() -> bool:
    session = _make_session("error-signal-group", target_from=target_group_prefix)
    QQBotContextManager.context[session.session_id] = object()
    client = _Client()
    try:
        with _ClientScope(client):
            await QQBotContextManager.error_signal(session)
        return client.api.calls == 0
    finally:
        QQBotContextManager.context.pop(session.session_id, None)


async def _test_hold_survives_inbound_processing() -> bool:
    """入站处理登记期间 hold 必须可用，即使平台已先撤销上下文。"""
    session = _make_session("hold-during-inbound-processing")
    QQBotContextManager.add_context(session, object())
    QQBotContextManager.activate_context(session)
    try:
        # 平台侧发送路径可能先撤销上下文，处理登记尚未结束。
        QQBotContextManager.del_context(session)
        QQBotContextManager.hold_context(session)
        held = QQBotContextManager.context_marks_hold.get(session.session_id) == 1
        QQBotContextManager.release_context(session)
        return held and session.session_id in QQBotContextManager.context
    finally:
        QQBotContextManager.context.pop(session.session_id, None)
        QQBotContextManager.context_marks_hold.pop(session.session_id, None)
        QQBotContextManager.context_marks_active.pop(session.session_id, None)


async def _test_hold_rejects_dropped_context_after_processing() -> bool:
    """处理登记结束并回收后，hold 仍须报告会话上下文不可用。"""
    session = _make_session("hold-after-inbound-processing")
    QQBotContextManager.add_context(session, object())
    QQBotContextManager.activate_context(session)
    QQBotContextManager.deactivate_context(session)
    QQBotContextManager.del_context(session)
    try:
        QQBotContextManager.hold_context(session)
        return False
    except SessionContextUnavailable:
        return True
    finally:
        QQBotContextManager.context.pop(session.session_id, None)
        QQBotContextManager.context_marks_hold.pop(session.session_id, None)
        QQBotContextManager.context_marks_active.pop(session.session_id, None)


async def _test_del_context_keeps_background_hold() -> bool:
    """入站处理结束后，仍被后台任务持有的上下文不得被回收。

    后台任务与入站处理的生命周期不同步：它在处理登记结束之后仍可能发起新的
    hold。此时删除上下文会让后续 hold 报告会话不可用。
    """
    session = _make_session("del-context-keeps-background-hold")
    ctx = object()
    QQBotContextManager.add_context(session, ctx)
    QQBotContextManager.activate_context(session)
    QQBotContextManager.hold_context(session)
    QQBotContextManager.deactivate_context(session)
    try:
        QQBotContextManager.del_context(session)
        kept = QQBotContextManager.context.get(session.session_id) is ctx
        QQBotContextManager.release_context(session)
        return kept and session.session_id not in QQBotContextManager.context
    finally:
        QQBotContextManager.context.pop(session.session_id, None)
        QQBotContextManager.context_marks_hold.pop(session.session_id, None)
        QQBotContextManager.context_marks_active.pop(session.session_id, None)


async def _test_release_keeps_rebuilt_context() -> bool:
    """释放 hold 时不得删除同一 session_id 重建的入站上下文。"""
    session = _make_session("release-keeps-rebuilt-context")
    QQBotContextManager.context_marks_hold[session.session_id] = 1
    QQBotContextManager.activate_context(session)
    rebuilt = object()
    QQBotContextManager.add_context(session, rebuilt)
    try:
        QQBotContextManager.release_context(session)
        return QQBotContextManager.context.get(session.session_id) is rebuilt
    finally:
        QQBotContextManager.context.pop(session.session_id, None)
        QQBotContextManager.context_marks_active.pop(session.session_id, None)


@func_case
async def test_qqbot_context_lifecycle_tolerance(tester: Tester):
    """bots.qqbot.context: 会话上下文回收后的 reaction 与错误信号容错"""
    await tester.test(_test_error_signal_skips_when_context_dropped, "错误信号在上下文缺失时静默返回")
    await tester.test(_test_error_signal_swallows_api_failure, "错误信号吞掉平台接口异常")
    await tester.test(_test_add_reaction_skips_when_context_dropped, "添加表情在上下文缺失时静默返回")
    await tester.test(_test_error_signal_ignores_non_guild_targets, "非频道会话不发错误信号")
    await tester.test(_test_hold_survives_inbound_processing, "入站处理登记期间 hold 不被删除竞速")
    await tester.test(_test_hold_rejects_dropped_context_after_processing, "处理结束后 hold 报告上下文不可用")
    await tester.test(_test_del_context_keeps_background_hold, "处理结束后仍被持有的上下文不被回收")
    await tester.test(_test_release_keeps_rebuilt_context, "释放 hold 不删除重建的入站上下文")
    return tester
