"""Telegram 更新的轻量上下文快照。"""

from attrs import define


@define(frozen=True, slots=True)
class TelegramContextSnapshot:
    chat_id: int
    chat_type: str
    user_id: int | None

    @classmethod
    def from_context(cls, context) -> "TelegramContextSnapshot":
        message = getattr(context, "message", None)
        if message is not None:
            chat = message.chat
            user = context.from_user
        else:
            chat = context.chat
            user = context.from_user
        return cls(
            chat_id=chat.id,
            chat_type=str(getattr(chat.type, "value", chat.type)),
            user_id=user.id if user else None,
        )
