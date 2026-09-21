import uuid

from core.utils.container import ExpiringTempDict

CONTEXT_EXPIRY = 600  # 上下文窗口有效期（秒）

_context_windows = ExpiringTempDict(exp=CONTEXT_EXPIRY)


def _new_session_id() -> str:
    return uuid.uuid4().hex[:8]


def create_context(messages: list[dict], context_key: str) -> str:
    """创建绑定场景的上下文快照，返回其 ID。"""
    session_id = _new_session_id()
    window = _context_windows[session_id]
    window["messages"] = messages
    window["context_key"] = context_key
    window.refresh()
    return session_id


def get_context(session_id: str | None, context_key: str) -> list[dict] | None:
    """获取同一场景的上下文历史；不存在、跨场景或已过期返回 None。"""
    if not session_id:
        return None
    window = _context_windows.data.get(session_id)
    if not isinstance(window, ExpiringTempDict) or window.is_expired():
        return None
    if window.data.get("context_key") != context_key:
        return None
    messages = window.data.get("messages")
    return messages if messages is not None else None


def refresh_context(session_id: str | None) -> bool:
    if not session_id:
        return False
    window = _context_windows.data.get(session_id)
    if not isinstance(window, ExpiringTempDict) or window.is_expired():
        return False
    window.refresh()
    return True
