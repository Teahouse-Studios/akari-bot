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
    :param refresh_token: 该用户的水鱼账号 refresh token
    :param subject: 水鱼用户 ID，即令牌响应中的 `sub`
    """

    union_scope = UNION_SCOPE_SENDER
    union_id = fields.CharField(max_length=512, primary_key=True)
    username = fields.CharField(max_length=512, default="")
    refresh_token = fields.CharField(max_length=1024, null=True)
    subject = fields.CharField(max_length=512, null=True)

    class Meta:
        table = f"{table_prefix}diving_prober_bind_info"

    @classmethod
    async def set_bind_info(
        cls,
        union_id: str,
        username: str,
        refresh_token: str | None = None,
        subject: str | None = None,
    ):
        async with union_mutation():
            async with in_transaction("default") as connection:
                current = await (
                    SenderUnionInfo.filter(union_id=union_id).using_db(connection).select_for_update().first()
                )
                if not current:
                    return False
                defaults = {"username": username}
                # 未提供令牌时不得把已有令牌写成空值：绑定信息也会自其它路径更新。
                if refresh_token is not None:
                    defaults["refresh_token"] = refresh_token
                if subject is not None:
                    defaults["subject"] = subject
                await cls.update_or_create(
                    union_id=union_id,
                    defaults=defaults,
                    using_db=connection,
                )
                return True

    @classmethod
    async def update_refresh_token(cls, union_id: str, refresh_token: str, subject: str | None = None):
        """回写轮换后的 refresh token。

        :param union_id: 用户联合 ID。
        :param refresh_token: 新签发的 refresh token。
        :param subject: 水鱼用户 ID，仅在响应中带上时更新。
        """
        defaults = {"refresh_token": refresh_token}
        if subject is not None:
            defaults["subject"] = subject
        return await cls.filter(union_id=union_id).update(**defaults)

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
    """maimai 落雪绑定信息表。

    :param union_id: 用户联合 ID
    :param refresh_token: 该用户的落雪账号 refresh token，仅 OAuth 授权后存在
    """

    union_scope = UNION_SCOPE_SENDER
    union_id = fields.CharField(max_length=512, primary_key=True)
    refresh_token = fields.CharField(max_length=1024, null=True)

    class Meta:
        table = f"{table_prefix}lxns_prober_bind_info"

    @classmethod
    async def set_bind_info(
        cls,
        union_id: str,
        refresh_token: str | None = None,
    ):
        async with union_mutation():
            async with in_transaction("default") as connection:
                current = await (
                    SenderUnionInfo.filter(union_id=union_id).using_db(connection).select_for_update().first()
                )
                if not current:
                    return False
                # 未提供令牌时没有可写的字段，不得把已有令牌写成空值。
                if refresh_token is None:
                    return True
                await cls.update_or_create(
                    union_id=union_id,
                    defaults={"refresh_token": refresh_token},
                    using_db=connection,
                )
                return True

    @classmethod
    async def update_refresh_token(cls, union_id: str, refresh_token: str):
        """回写轮换后的 refresh token。

        :param union_id: 用户联合 ID。
        :param refresh_token: 新签发的 refresh token。
        """
        return await cls.filter(union_id=union_id).update(refresh_token=refresh_token)

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
