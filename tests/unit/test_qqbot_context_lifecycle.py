"""QQBot 会话上下文回收后 reaction 与错误信号的容错测试。"""

from bots.qqbot.context import QQBotContextManager
from bots.qqbot.info import target_guild_prefix, target_group_prefix
from core.builtins.session.info import SessionInfo
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


async def _test_remove_reaction_skips_when_context_dropped() -> bool:
    session = _make_session("remove-reaction-context-dropped", target_from=target_guild_prefix)
    QQBotContextManager.context.pop(session.session_id, None)
    with _ClientScope(None):
        try:
            await QQBotContextManager.remove_reaction(session, ["m1"], "1")
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


@func_case
async def test_qqbot_context_lifecycle_tolerance(tester: Tester):
    """bots.qqbot.context: 会话上下文回收后的 reaction 与错误信号容错"""
    await tester.test(_test_error_signal_skips_when_context_dropped, "错误信号在上下文缺失时静默返回")
    await tester.test(_test_error_signal_swallows_api_failure, "错误信号吞掉平台接口异常")
    await tester.test(_test_add_reaction_skips_when_context_dropped, "添加表情在上下文缺失时静默返回")
    await tester.test(_test_remove_reaction_skips_when_context_dropped, "移除表情在上下文缺失时静默返回")
    await tester.test(_test_error_signal_ignores_non_guild_targets, "非频道会话不发错误信号")
    return tester
