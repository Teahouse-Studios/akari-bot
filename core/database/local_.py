import os
import hashlib
import datetime

import orjson as json
from tortoise import fields, Tortoise
from tortoise.models import Model
from tortoise.transactions import in_transaction
from tortoise.exceptions import OperationalError
from tenacity import retry, stop_after_attempt

from core.constants.path import database_path

os.makedirs(database_path, exist_ok=True)

DB_LINK = "sqlite:///database/local.db"

datetime = datetime.datetime

class DirtyFilterTable(Model):
    __table__ = "filter_cache"
    desc = fields.TextField(primary_key=True)
    result = fields.TextField()
    timestamp = fields.DatetimeField(auto_now=True)

class CrowdinActivityRecordsTable(Model):
    __table__ = "crowdin_activity_records"
    hash_id = fields.TextField(primary_key=True)

async def init_db():
    await Tortoise.init(
        db_url=DB_LINK,
        modules={'models': ['__main__']}
    )
    await Tortoise.generate_schemas()

class DirtyWordCache:
    def __init__(self, query_word):
        self.query_word = query_word

    async def get(self):
        try:
            dirty_filter, _ = await DirtyFilterTable.get_or_create(desc=self.query_word)
            return json.loads(dirty_filter.result) if dirty_filter.result else False
        except OperationalError as e:
            print(f"Database error: {e}")
            return False

    @retry(stop=stop_after_attempt(3))
    async def update(self, result: dict):
        async with in_transaction() as conn:
            dirty_filter, created = await DirtyFilterTable.get_or_create(desc=self.query_word, _transaction=conn)
            if not created:
                dirty_filter.timestamp = datetime.now()
            dirty_filter.result = json.dumps(result).decode()
            await dirty_filter.save()

class CrowdinActivityRecords:

    @staticmethod
    @retry(stop=stop_after_attempt(3))
    async def check(txt: str):
        query_hash = hashlib.md5(
            txt.encode('utf-8'), usedforsecurity=False
        ).hexdigest()
        record = await CrowdinActivityRecordsTable.get_or_create(hash_id=query_hash)
        return record is not None

if __name__ == '__main__':
    import asyncio
    asyncio.run(init_db())
