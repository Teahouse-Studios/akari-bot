import uuid

from core.utils.container import ExpiringTempDict

CONTEXT_EXPIRY = 600  # 上下文窗口有效期（秒）

_context_windows = ExpiringTempDict(exp=CONTEXT_EXPIRY)


def _new_session_id() -> str:
    return uuid.uuid4().hex[:8]


def create_context(messages: list[dict]) -> str:
    """创建新的上下文窗口，返回其 ID。"""
    session_id = _new_session_id()
    window = _context_windows[session_id]
    window["messages"] = messages
    window.refresh()
    return session_id


def get_context(session_id: str | None) -> list[dict] | None:
    """获取上下文窗口的对话历史；不存在或已过期返回 None。"""
    if not session_id:
        return None
    window = _context_windows.data.get(session_id)
    if not isinstance(window, ExpiringTempDict) or window.is_expired():
        return None
    messages = window.data.get("messages")
    return messages if messages is not None else None


def refresh_context(session_id: str | None) -> bool:
    """会话被成功续写时仅重置其过期计时，历史保持不变；不存在或已过期返回 False。

    会话一旦创建即视为不可变的快照：续写时生成新的会话 ID 以支持分叉，
    这里只负责在父会话被成功继续时刷新其有效期。
    """
    if not session_id:
        return False
    window = _context_windows.data.get(session_id)
    if not isinstance(window, ExpiringTempDict) or window.is_expired():
        return False
    window.refresh()
    return True
