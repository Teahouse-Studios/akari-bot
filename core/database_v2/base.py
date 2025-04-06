from tortoise.models import Model
from typing import TYPE_CHECKING, Union, Self

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
    ) -> Self:
        """
        Get a model by target_id.
        """
        t = target_id
        if isinstance(target_id, (exports['Bot'].MessageSession, exports['Bot'].FetchedSession)):
            t = t.target.target_id
        return (await cls.get_or_create(target_id=t))[0]



    @classmethod
    async def get_by_sender_id(cls,
        sender_id: Union["Bot.MessageSession", "Bot.FetchedSession", str],
    ) -> Self:
        """
        Get a model by sender_id.
        """
        t = sender_id
        if isinstance(sender_id, (exports['Bot'].MessageSession, exports['Bot'].FetchedSession)):
            t = t.target.sender_id
        return (await cls.get_or_create(sender_id=t))[0]




