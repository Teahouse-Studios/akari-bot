"""Cross-platform bot membership and permission state."""

from typing import Any

from attrs import define, field


@define
class BotState:
    """A serializable snapshot of the bot in the current context."""

    available: bool | None = None
    joined: bool | None = None
    is_owner: bool | None = None
    is_admin: bool | None = None
    can_read_messages: bool | None = None
    can_read_all_messages: bool | None = None
    can_send_messages: bool | None = None
    can_send_proactive_messages: bool | None = None
    can_manage_messages: bool | None = None
    can_manage_members: bool | None = None
    can_restrict_members: bool | None = None
    can_react: bool | None = None
    can_send_private_messages: bool | None = None
    permissions: dict[str, Any] = field(factory=dict)
    raw: dict[str, Any] = field(factory=dict)
    error: str | None = None

    def has_permission(self, name: str, default: bool | None = None) -> bool | None:
        """Return a platform-specific permission, preserving unknown values."""
        value = self.permissions.get(name, default)
        return value if isinstance(value, bool) or value is None else default


__all__ = ["BotState"]
