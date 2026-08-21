from tortoise import fields
from tortoise.transactions import in_transaction

from core.database.base import DBModel
from core.database.models import SenderUnionInfo, UNION_SCOPE_SENDER, union_mutation

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
        async with union_mutation():
            async with in_transaction("default") as connection:
                current = await (
                    SenderUnionInfo.filter(union_id=union_id).using_db(connection).select_for_update().first()
                )
                if not current:
                    return False
                await cls.update_or_create(
                    union_id=union_id,
                    defaults={"username": username},
                    using_db=connection,
                )
                return True

    @classmethod
    async def remove_bind_info(cls, union_id):
        async with union_mutation():
            async with in_transaction("default") as connection:
                current = await (
                    SenderUnionInfo.filter(union_id=union_id).using_db(connection).select_for_update().first()
                )
                if not current:
                    return False
                await cls.filter(union_id=union_id).using_db(connection).delete()
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
        async with union_mutation():
            async with in_transaction("default") as connection:
                current = await (
                    SenderUnionInfo.filter(union_id=union_id).using_db(connection).select_for_update().first()
                )
                if not current:
                    return False
                await cls.update_or_create(
                    union_id=union_id,
                    defaults={"friend_code": friend_code},
                    using_db=connection,
                )
                return True

    @classmethod
    async def remove_bind_info(cls, union_id):
        async with union_mutation():
            async with in_transaction("default") as connection:
                current = await (
                    SenderUnionInfo.filter(union_id=union_id).using_db(connection).select_for_update().first()
                )
                if not current:
                    return False
                await cls.filter(union_id=union_id).using_db(connection).delete()
                return True
