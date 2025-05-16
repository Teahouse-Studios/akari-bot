from datetime import datetime, timedelta, UTC
import hashlib
import os
import secrets

from tortoise import fields

from core.constants.path import database_path
from .base import DBModel


os.makedirs(database_path, exist_ok=True)

CSRF_TOKEN_EXPIRY = 3600
DB_LINK = "sqlite://database/local.db"


class CSRFTokenRecords(DBModel):
    csrf_token = fields.CharField(pk=True, max_length=128, unique=True)
    device_token = fields.CharField(max_length=512)
    timestamp = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "csrf_token_records"

    @classmethod
    async def generate_csrf_token(cls, device_token: str) -> str:
        csrf_token = secrets.token_hex(32)

        expiry_time = datetime.now(UTC) - timedelta(seconds=CSRF_TOKEN_EXPIRY)
        await cls.filter(timestamp__lt=expiry_time).delete()

        await cls.create(
            csrf_token=csrf_token,
            device_token=device_token,
        )
        return csrf_token


class DirtyWordCache(DBModel):
    desc = fields.TextField(pk=True)
    result = fields.JSONField(default={})
    timestamp = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "dirty_word_cache"

    @classmethod
    async def check(cls, query_word):
        query = await cls.filter(desc=query_word).first()

        if query and datetime.now().timestamp() - query.timestamp.timestamp() > 86400:
            await query.delete()

        return query


class CrowdinActivityRecords(DBModel):
    hash_id = fields.TextField(pk=True)

    class Meta:
        table = "crowdin_activity_records"

    @classmethod
    async def check(cls, txt: str):
        query_hash = hashlib.sha256(txt.encode(encoding="UTF-8")).hexdigest()

        query = await cls.filter(hash_id=query_hash).first()
        if not query:
            query = await cls.create(hash_id=query_hash)
            await query.save()
            return False
        return True
