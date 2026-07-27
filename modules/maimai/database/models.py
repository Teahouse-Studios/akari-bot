from tortoise import fields

from core.database.base import DBModel
from core.database.models import UNION_SCOPE_SENDER

table_prefix = "module_maimai_"


class DivingProberBindInfo(DBModel):
    """
    maimai 水鱼绑定信息表。

    :param union_id: 用户联合 ID
    :param username: 用户名
    """

    union_scope = UNION_SCOPE_SENDER
    union_id = fields.CharField(max_length=512, primary_key=True)
    username = fields.CharField(max_length=512)

    class Meta:
        table = f"{table_prefix}diving_prober_bind_info"

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


class LxnsProberBindInfo(DBModel):
    """
    maimai 落雪绑定信息表。

    :param union_id: 用户联合 ID
    :param friend_code: 好友码
    """

    union_scope = UNION_SCOPE_SENDER
    union_id = fields.CharField(max_length=512, primary_key=True)
    friend_code = fields.CharField(max_length=512)

    class Meta:
        table = f"{table_prefix}lxns_prober_bind_info"

    @classmethod
    async def set_bind_info(cls, union_id: str, friend_code: str):
        exist_info = await cls.get_or_none(union_id=union_id)
        if exist_info:
            await exist_info.delete()
        bind_info = (await cls.get_or_create(union_id=union_id, friend_code=friend_code))[0]
        await bind_info.save()
        return True

    @classmethod
    async def remove_bind_info(cls, union_id):
        bind_info = await cls.get_or_none(union_id=union_id)
        if bind_info:
            await bind_info.delete()
        return True
