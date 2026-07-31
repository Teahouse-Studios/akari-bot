from tortoise import fields

from core.database.base import DBModel
from core.database.models import UNION_SCOPE_SENDER

table_prefix = "module_cytoid_"


class CytoidBindInfo(DBModel):
    """
    Cytoid 用户绑定信息。

    :param union_id: 绑定的用户联合 ID。
    :param username: 绑定的用户名。
    """

    union_scope = UNION_SCOPE_SENDER
    union_id = fields.CharField(max_length=512, primary_key=True)
    username = fields.CharField(max_length=512)

    class Meta:
        table = f"{table_prefix}bind_info"

    @classmethod
    async def set_bind_info(cls, union_id: str, username: str):
        exist_info = await cls.get_or_none(union_id=union_id)
        if exist_info:
            await exist_info.delete()
        bind_info = (await cls.get_or_create(union_id=union_id, username=username))[0]
        await bind_info.save()
        return True

    @classmethod
    async def remove_bind_info(cls, union_id):
        bind_info = await cls.get_or_none(union_id=union_id)
        if bind_info:
            await bind_info.delete()
        return True
