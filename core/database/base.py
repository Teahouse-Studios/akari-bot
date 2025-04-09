from typing import TYPE_CHECKING, Union, Self

from tortoise.models import Model

from core.exports import exports

if TYPE_CHECKING:
    from core.builtins import Bot


class DBModel(Model):
    """
    Base model for all database models.
    """

    class Meta:
        abstract = True

    @classmethod
    async def get_by_target_id(cls,
                               target_id: Union["Bot.MessageSession", "Bot.FetchedSession", str],
                               create: bool = True
                               ) -> Self:
        """
        Get a model by target_id.

        :param target_id: The target_id to search for.
        :param create: Whether to create a new model if it doesn\'t exist.
        :return: The model instance. If create is True and the model doesn"t exist, a new instance will be created, otherwise None.

        """
        t = target_id
        if isinstance(target_id, (exports["Bot"].MessageSession, exports["Bot"].FetchedSession)):
            t = t.target.target_id
        if create:
            return (await cls.get_or_create(target_id=t))[0]
        return await cls.get_or_none(target_id=t)

    @classmethod
    async def get_by_sender_id(cls,
                               sender_id: Union["Bot.MessageSession", "Bot.FetchedSession", str],
                               create: bool = True
                               ) -> Self:
        """
        Get a model by sender_id.

        :param sender_id: The sender_id to search for.
        :param create: Whether to create a new model if it doesn\'t exist.
        :return: The model instance. If create is True and the model doesn"t exist, a new instance will be created, otherwise None.
        """
        t = sender_id
        if isinstance(sender_id, (exports["Bot"].MessageSession, exports["Bot"].FetchedSession)):
            t = t.target.sender_id
        if create:
            return (await cls.get_or_create(sender_id=t))[0]
        return await cls.get_or_none(sender_id=t)
