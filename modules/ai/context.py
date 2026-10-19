import uuid

from core.utils.container import ExpiringTempDict

CONTEXT_EXPIRY = 1000  # 上下文窗口有效期（秒）

_context_windows = ExpiringTempDict(exp=CONTEXT_EXPIRY)


def _new_session_id() -> str:
    return uuid.uuid4().hex[:8]


def _get_window(session_id: str | None, context_key: str) -> ExpiringTempDict | None:
    if not session_id:
        return None
    window = _context_windows.data.get(session_id)
    if not isinstance(window, ExpiringTempDict) or window.is_expired():
        return None
    if window.data.get("context_key") != context_key:
        return None
    return window


def create_context(messages: list[dict], context_key: str, llm: str | None = None) -> str:
    """创建绑定场景的上下文快照，返回其 ID。"""
    session_id = _new_session_id()
    window = _context_windows[session_id]
    window["messages"] = messages
    window["context_key"] = context_key
    if llm:
        window["llm"] = llm
    window.refresh()
    return session_id


def get_context(session_id: str | None, context_key: str) -> list[dict] | None:
    """获取同一场景的上下文历史；不存在、跨场景或已过期返回 None。"""
    window = _get_window(session_id, context_key)
    if window is None:
        return None
    messages = window.data.get("messages")
    return messages if messages is not None else None


def get_context_llm(session_id: str | None, context_key: str) -> str | None:
    """获取上下文快照使用的模型名称；不存在、跨场景或已过期返回 None。"""
    window = _get_window(session_id, context_key)
    if window is None:
        return None
    llm = window.data.get("llm")
    return llm if isinstance(llm, str) else None


def refresh_context(session_id: str | None) -> bool:
    if not session_id:
        return False
    window = _context_windows.data.get(session_id)
    if not isinstance(window, ExpiringTempDict) or window.is_expired():
        return False
    window.refresh()
    return True
