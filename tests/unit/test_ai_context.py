"""modules.ai.context 上下文窗口单元测试。"""

from unittest.mock import patch

from core.tester import func_case, Tester
from modules.ai import context


def _test_context_isolated_by_context_key_and_can_branch():
    with patch.object(context, "_context_windows", context.ExpiringTempDict(exp=context.CONTEXT_EXPIRY)):
        parent_id = context.create_context([{"role": "user", "content": "start"}], "context-a")
        child_id = context.create_context(
            [{"role": "user", "content": "start"}, {"role": "assistant", "content": "reply"}], "context-a"
        )

        assert context.get_context(parent_id, "context-a") == [{"role": "user", "content": "start"}]
        assert context.get_context(child_id, "context-a")[1]["content"] == "reply"
        assert context.get_context(parent_id, "context-b") is None
    return True


@func_case
async def test_ai_context(tester: Tester):
    """modules.ai.context: 上下文窗口隔离与快照分叉测试"""
    await tester.test(_test_context_isolated_by_context_key_and_can_branch, "上下文按场景隔离与快照分叉测试")
    return tester
