from tortoise.models import Model
from tortoise import fields

table_prefix = "module_maimai_"


class DivingProberBindInfo(Model):
    sender_id = fields.CharField(max_length=512, pk=True)
    username = fields.CharField(max_length=512)

    class Meta:
        table = f"{table_prefix}diving_prober_bind_info"

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
