import hashlib
import time

from tortoise import fields

from core.constants.path import database_path
from .base import DBModel

database_path.mkdir(parents=True, exist_ok=True)

DB_LINK = "sqlite://database/local.db"


class DirtyWordCache(DBModel):
    desc = fields.CharField(max_length=512, primary_key=True)
    result = fields.JSONField(default={})
    timestamp = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "dirty_word_cache"

    @classmethod
    async def check(cls, query_word):
        query = await cls.filter(desc=query_word).first()

        if query and time.time() - query.timestamp.timestamp() > 86400:
            await query.delete()

        return query


class CrowdinActivityRecords(DBModel):
    hash_id = fields.CharField(max_length=512, primary_key=True)

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
