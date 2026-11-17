from tortoise import fields
from tortoise.transactions import in_transaction

from core.database.base import DBModel
from core.database.models import SenderUnionInfo, UNION_SCOPE_SENDER, union_mutation

table_prefix = "module_phigros_"


class PhigrosBindInfo(DBModel):
    """
    Phigros 用户绑定信息表

    :param union_id: 用户联合 ID
    :param session_token: 会话令牌
    :param username: 玩家昵称
    :param is_international: 是否为国际服账号
    """

    union_scope = UNION_SCOPE_SENDER
    union_id = fields.CharField(max_length=512, primary_key=True)
    session_token = fields.CharField(max_length=512)
    username = fields.CharField(max_length=512)
    is_international = fields.BooleanField(default=False)

    class Meta:
        table = f"{table_prefix}bind_info"

    @classmethod
    async def set_bind_info(
        cls,
        union_id: str,
        session_token: str,
        username: str = "Guest",
        is_international: bool = False,
    ):
        async with union_mutation():
            async with in_transaction("default") as connection:
                current = await (
                    SenderUnionInfo.filter(union_id=union_id).using_db(connection).select_for_update().first()
                )
                if not current:
                    return False
                await cls.update_or_create(
                    union_id=union_id,
                    defaults={
                        "session_token": session_token,
                        "username": username,
                        "is_international": is_international,
                    },
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
