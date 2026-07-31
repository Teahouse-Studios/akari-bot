from tortoise import fields

from core.database.base import DBModel
from core.database.models import UNION_SCOPE_SENDER

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
        exist_info = await cls.get_or_none(union_id=union_id)
        if exist_info:
            await exist_info.delete()
        bind_info = (
            await cls.get_or_create(
                union_id=union_id,
                session_token=session_token,
                username=username,
                is_international=is_international,
            )
        )[0]
        await bind_info.save()
        return True

    @classmethod
    async def remove_bind_info(cls, union_id):
        bind_info = await cls.get_or_none(union_id=union_id)
        if bind_info:
            await bind_info.delete()
        return True
