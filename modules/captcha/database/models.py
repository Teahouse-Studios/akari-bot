import hashlib
from typing import ClassVar

from tortoise import fields

from core.database.base import DBModel
from core.database.models import UNION_SCOPE_SENDER, UNION_SCOPE_TARGET


def _verification_id(target_union_id: str, sender_union_id: str) -> str:
    return hashlib.sha256(f"{target_union_id}\0{sender_union_id}".encode()).hexdigest()


class CaptchaTrust(DBModel):
    """按场景与用户 union 隔离的入群验证信任记录。"""

    trust_id = fields.CharField(max_length=64, primary_key=True)
    target_union_id = fields.CharField(max_length=512, db_index=True)
    sender_union_id = fields.CharField(max_length=512, db_index=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "module_captcha_trust"

    @classmethod
    async def migrate_union_reference(cls, scope: str, from_union: str, to_union: str) -> None:
        field = "sender_union_id" if scope == UNION_SCOPE_SENDER else "target_union_id"
        if scope not in {UNION_SCOPE_SENDER, UNION_SCOPE_TARGET}:
            return

        for trust in await cls.filter(**{field: from_union}):
            target_union_id = to_union if scope == UNION_SCOPE_TARGET else trust.target_union_id
            sender_union_id = to_union if scope == UNION_SCOPE_SENDER else trust.sender_union_id
            await cls.get_or_create(
                trust_id=_verification_id(target_union_id, sender_union_id),
                defaults={
                    "target_union_id": target_union_id,
                    "sender_union_id": sender_union_id,
                },
            )
            await trust.delete()

    @classmethod
    async def delete_union_reference(cls, scope: str, union_id: str) -> None:
        field = "sender_union_id" if scope == UNION_SCOPE_SENDER else "target_union_id"
        if scope in {UNION_SCOPE_SENDER, UNION_SCOPE_TARGET}:
            await cls.filter(**{field: union_id}).delete()


class CaptchaChallenge(DBModel):
    """待处理的入群验证码及其平台操作路由快照。"""

    challenge_id = fields.CharField(max_length=64, primary_key=True)
    target_union_id = fields.CharField(max_length=512, db_index=True)
    sender_union_id = fields.CharField(max_length=512, db_index=True)
    target_id = fields.CharField(max_length=512)
    sender_id = fields.CharField(max_length=512)
    token = fields.CharField(max_length=128, unique=True)
    answer = fields.IntField()
    choices = fields.JSONField(default=[])
    status = fields.CharField(max_length=32, default="preparing", db_index=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)
    verified_at = fields.DatetimeField(null=True, default=None)

    class Meta:
        table = "module_captcha_challenge"

    ACTIVE_STATUSES: ClassVar[set[str]] = {"preparing", "pending", "failed"}

    @classmethod
    async def validate_union_delete(cls, scope: str, union_id: str) -> str | None:
        field = "sender_union_id" if scope == UNION_SCOPE_SENDER else "target_union_id"
        if scope not in {UNION_SCOPE_SENDER, UNION_SCOPE_TARGET}:
            return None
        if await cls.filter(**{field: union_id, "status__in": cls.ACTIVE_STATUSES}).exists():
            return "active captcha challenge still requires platform restriction cleanup"
        return None

    @classmethod
    async def migrate_union_reference(cls, scope: str, from_union: str, to_union: str) -> None:
        field = "sender_union_id" if scope == UNION_SCOPE_SENDER else "target_union_id"
        if scope in {UNION_SCOPE_SENDER, UNION_SCOPE_TARGET}:
            # challenge_id 只作为稳定记录 ID 使用。迁移后可能有多条历史挑战落到同一组合，
            # 保留原主键可避免碰撞；新事件按两个 Union 字段查询，不再假定主键等于组合哈希。
            await cls.filter(**{field: from_union}).update(**{field: to_union})

    @classmethod
    async def migrate_unbound_union_reference(
        cls,
        scope: str,
        platform_id: str,
        from_union: str,
        to_union: str,
    ) -> None:
        """把被拆出平台成员仍需处理的挑战改挂到其新 Union。

        已验证挑战和信任属于正向状态，不随“从零开始”的解绑继承；仍处于准备、
        等待或失败状态的挑战对应真实的平台禁言，必须跟随其 ``sender_id`` 或
        ``target_id``，否则用户会永久无法用原 token 解禁。
        """
        if scope == UNION_SCOPE_SENDER:
            await cls.filter(
                sender_union_id=from_union,
                sender_id=platform_id,
                status__in=cls.ACTIVE_STATUSES,
            ).update(sender_union_id=to_union)
        elif scope == UNION_SCOPE_TARGET:
            await cls.filter(
                target_union_id=from_union,
                target_id=platform_id,
                status__in=cls.ACTIVE_STATUSES,
            ).update(target_union_id=to_union)

    @classmethod
    async def delete_union_reference(cls, scope: str, union_id: str) -> None:
        field = "sender_union_id" if scope == UNION_SCOPE_SENDER else "target_union_id"
        if scope in {UNION_SCOPE_SENDER, UNION_SCOPE_TARGET}:
            await cls.filter(**{field: union_id}).delete()


__all__ = ["CaptchaTrust", "CaptchaChallenge"]
