import uuid

from core.utils.container import ExpiringTempDict

CONTEXT_EXPIRY = 600  # 上下文窗口有效期（秒）

_context_windows = ExpiringTempDict(exp=CONTEXT_EXPIRY)


def _new_context_id() -> str:
    return uuid.uuid4().hex[:8]


def create_context(messages: list[dict]) -> str:
    """创建新的上下文窗口，返回其 ID。"""
    context_id = _new_context_id()
    window = _context_windows[context_id]
    window["messages"] = messages
    window.refresh()
    return context_id


def get_context(context_id: str | None) -> list[dict] | None:
    """获取上下文窗口的对话历史；不存在或已过期返回 None。"""
    if not context_id:
        return None
    window = _context_windows.data.get(context_id)
    if not isinstance(window, ExpiringTempDict) or window.is_expired():
        return None
    messages = window.data.get("messages")
    return messages if messages is not None else None


def update_context(context_id: str, messages: list[dict]) -> bool:
    """更新上下文窗口的对话历史并重置计时；不存在或已过期返回 False。"""
    window = _context_windows.data.get(context_id)
    if not isinstance(window, ExpiringTempDict) or window.is_expired():
        return False
    window.data["messages"] = messages
    window.refresh()
    return True
