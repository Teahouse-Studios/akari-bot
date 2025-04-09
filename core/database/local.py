from datetime import datetime
import hashlib
import os

from tortoise.models import Model
from tortoise import fields

from core.constants.path import database_path


os.makedirs(database_path, exist_ok=True)

DB_LINK = "sqlite://database/local.db"


class DirtyWordCache(Model):
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


class CrowdinActivityRecords(Model):
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


__all__ = [
    "DirtyWordCache",
    "CrowdinActivityRecords",
]
