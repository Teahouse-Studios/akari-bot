from tortoise import fields

from core.database.base import DBModel

table_prefix = "module_osu_"


class OsuBindInfo(DBModel):
    """
    Osu 用户绑定信息表

    :param sender_id: 用户 ID
    :param username: osu 用户名
    """

    sender_id = fields.CharField(max_length=512, pk=True)
    username = fields.CharField(max_length=512)

    class Meta:
        table = f"{table_prefix}bind_info"

    @classmethod
    async def set_bind_info(cls, sender_id: str, username: str):
        bind_info = (await cls.get_or_create(sender_id=sender_id, username=username))[0]
        await bind_info.save()
        return True

    @classmethod
    async def remove_bind_info(cls, sender_id):
        bind_info = await cls.get_or_none(sender_id=sender_id)
        if bind_info:
            await bind_info.delete()
        return True
