from tortoise.models import Model
from tortoise import fields

table_prefix = "module_cytoid_"


class CytoidBindInfo(Model):
    """
    Cytoid 用户绑定信息。

    :param sender_id: 绑定的用户 ID。
    :param username: 绑定的用户名。
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
