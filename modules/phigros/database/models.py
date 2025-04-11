from tortoise.models import Model
from tortoise import fields

table_prefix = "module_phigros_"


class PhigrosBindInfo(Model):
    """
    Phigros 用户绑定信息表

    :param sender_id: 用户 ID
    :param session_token: 会话令牌
    """
    sender_id = fields.CharField(max_length=512, pk=True)
    session_token = fields.CharField(max_length=512)
    username = fields.CharField(max_length=512)

    class Meta:
        table = f"{table_prefix}bind_info"

    @classmethod
    async def set_bind_info(cls, sender_id: str, session_token: str, username: str = "Guest"):
        bind_info = (await cls.get_or_create(sender_id=sender_id, session_token=session_token, username=username))[0]
        await bind_info.save()
        return True

    @classmethod
    async def remove_bind_info(cls, sender_id):
        bind_info = await cls.get_or_none(sender_id=sender_id)
        if bind_info:
            await bind_info.delete()
        return True
