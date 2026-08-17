from tortoise import fields

from core.database.base import DBModel


class CaptchaTrust(DBModel):
    """按场景与用户 union 隔离的入群验证信任记录。"""

    trust_id = fields.CharField(max_length=64, primary_key=True)
    target_union_id = fields.CharField(max_length=512, db_index=True)
    sender_union_id = fields.CharField(max_length=512, db_index=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "module_captcha_trust"


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


__all__ = ["CaptchaTrust", "CaptchaChallenge"]
