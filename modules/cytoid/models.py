from tortoise.models import Model
from tortoise import fields
from core.builtins import Bot

table_prefix = "module_cytoid_"

class CytoidBindInfo(Model):
    target_id = fields.IntField(pk=True)
    username = fields.CharField(max_length=512)
    class Meta:
        name = table_prefix + "CytoidBindInfo"

    @classmethod
    async def remove_bind_info(cls, msg: Bot.MessageSession):
        await cls.filter(target_id=msg.target.target_id).delete()
        return True
