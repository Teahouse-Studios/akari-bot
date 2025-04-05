from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

import orjson as json
from tortoise import fields
from tortoise.exceptions import DoesNotExist
from tortoise.models import Model

table_prefix = "module_wiki_"


class WikiTargetInfo(Model):
    target_id = fields.CharField(max_length=512, pk=True)
    api_link = fields.CharField(max_length=512, null=True)
    interwikis = fields.JSONField(default={})
    headers = fields.JSONField(default={"accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6"})
    prefix = fields.CharField(max_length=512, null=True)

    class Meta:
        table = f"{table_prefix}target_set_info"

    async def add_start_wiki(self, url: str):
        self.api_link = url
        await self.save()
        return True

    async def config_interwikis(self, iw: str, iwlink: Optional[str] = None):
        interwikis = self.interwikis
        if iwlink:
            interwikis[iw] = iwlink
        else:
            if iw in interwikis:
                del interwikis[iw]
        self.interwikis = interwikis
        await self.save()
        return True

    async def config_headers(self, headers: Optional[str] = None, add: bool = True):
        try:
            headers_ = self.headers
            if headers and add:
                headers = json.loads(headers)
                for x in headers:
                    headers_[x] = headers[x]
            elif headers:
                headers_ = {k: v for k, v in headers_.items() if k not in headers}
            else:
                headers_ = {}
            self.headers = headers_
            await self.save()
            return True
        except Exception:
            return False

    async def config_prefix(self, prefix: Optional[str] = None):
        self.prefix = prefix
        await self.save()
        return True


class WikiSiteInfo(Model):
    api_link = fields.CharField(max_length=512, pk=True)
    site_info = fields.JSONField(default={})
    timestamp = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = f"{table_prefix}wiki_info"

    async def update(self, info: dict):
        try:
            query = await WikiSiteInfo.get(api_link=self.api_link)
            query.site_info = json.dumps(info)
            query.timestamp = datetime.now()
            await query.save()
        except DoesNotExist:
            await WikiSiteInfo.create(api_link=self.api_link, site_info=json.dumps(info), timestamp=datetime.now())

        return True

    @classmethod
    def get_like_this(cls, t: str):
        return cls.filter(cls.api_link.like(f"%{t}%")).first()


class WikiAllowList(Model):
    api_link = fields.CharField(max_length=512, pk=True)
    timestamp = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = f"{table_prefix}wiki_allow_list"

    @classmethod
    async def check(cls, api_link) -> bool:
        api_link = urlparse(api_link).netloc
        return bool(await cls.filter(api_link=api_link).first())

    @classmethod
    async def add(cls, api_link) -> bool:
        if await cls.filter(api_link=api_link).exists():
            return False
        await cls.create(api_link=api_link)
        return True

    @classmethod
    async def remove(cls, api_link) -> bool:
        if not await cls.filter(api_link=api_link).exists():
            return False
        await cls.filter(api_link=api_link).delete()
        return True


class WikiBlockList(Model):
    api_link = fields.CharField(max_length=512, pk=True)
    timestamp = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = f"{table_prefix}wiki_block_list"

    @classmethod
    async def check(cls, api_link: str) -> bool:
        api_link = urlparse(api_link).netloc
        return await cls.filter(api_link=api_link).exists()

    @classmethod
    async def add(cls, api_link) -> bool:
        if await cls.filter(api_link=api_link).exists():
            return False
        await cls.create(api_link=api_link)
        return True

    @classmethod
    async def remove(cls, api_link) -> bool:
        if not await cls.filter(api_link=api_link).exists():
            return False
        await cls.filter(api_link=api_link).delete()
        return True


class WikiBotAccountList(Model):
    api_link = fields.CharField(max_length=512, pk=True)
    bot_account = fields.CharField(max_length=512)
    bot_password = fields.CharField(max_length=512)

    class Meta:
        table = f"{table_prefix}wiki_bot_account"

    @classmethod
    async def add(cls, api_link: str, bot_account: str, bot_password: str):
        if await cls.filter(api_link=api_link):
            return False

        await cls.create(api_link=api_link,
                         bot_account=bot_account,
                         bot_password=bot_password)
        return True

    @classmethod
    async def remove(cls, api_link):
        queries = await cls.filter(api_link=api_link)
        if not queries:
            return False

        await queries[0].delete()
        return True
