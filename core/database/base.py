from typing import Self, TYPE_CHECKING

from tortoise.models import Model

from core.exports import exports

if TYPE_CHECKING:
    from core.builtins.bot import Bot


def _extract_id(value, attr: str) -> str | None:
    """
    从字符串或会话对象中取出 ID。

    :param value: ID 字符串或 MessageSession / FetchedMessageSession 实例。
    :param attr: 要读取的 SessionInfo 属性名。
    """
    if isinstance(value, str):
        return value
    if ex := exports.get("Bot"):
        ex: "Bot"
        if isinstance(value, (ex.MessageSession, ex.FetchedMessageSession)):
            return getattr(value.session_info, attr)
    return None


class DBModel(Model):
    """
    Base model for all database models.
    """

    class Meta:
        abstract = True

    @classmethod
    async def get_by_target_id(
        cls, target_id: "Bot.MessageSession | Bot.FetchedMessageSession | str", create: bool = True
    ) -> Self | None:
        """
        Get a model by target_id.

        The target_id is resolved into its union_id first, so all data is keyed by union rather than by platform id.

        :param target_id: The target_id to search for.
        :param create: Whether to create a new model if it doesn't exist.
        :return: The model instance. If create is True and the model doesn't exist, a new instance will be created, otherwise None.

        """
        from .models import TargetInfo

        t = _extract_id(target_id, "target_id")
        if not t:
            raise ValueError(
                "target_id must be a str or a MessageSession/FetchedMessageSession instance, or exports are unavailable."
            )
        if cls is TargetInfo:
            return await TargetInfo.resolve_union(t, create)

        union = await TargetInfo.resolve_union(t, create)
        if not union:
            return None
        if create:
            return (await cls.get_or_create(union_id=union.union_id))[0]
        return await cls.get_or_none(union_id=union.union_id)

    @classmethod
    async def get_by_sender_id(
        cls, sender_id: "Bot.MessageSession | Bot.FetchedMessageSession | str", create: bool = True
    ) -> Self | None:
        """
        Get a model by sender_id.

        The sender_id is resolved into its union_id first, so all data is keyed by union rather than by platform id.

        :param sender_id: The sender_id to search for.
        :param create: Whether to create a new model if it doesn't exist.
        :return: The model instance. If create is True and the model doesn't exist, a new instance will be created, otherwise None.
        """
        from .models import SenderInfo

        t = _extract_id(sender_id, "sender_id")
        if not t:
            raise ValueError(
                "sender_id must be a str or a MessageSession/FetchedMessageSession instance, or exports are unavailable."
            )
        if cls is SenderInfo:
            return await SenderInfo.resolve_union(t, create)

        union = await SenderInfo.resolve_union(t, create)
        if not union:
            return None
        if create:
            return (await cls.get_or_create(union_id=union.union_id))[0]
        return await cls.get_or_none(union_id=union.union_id)
