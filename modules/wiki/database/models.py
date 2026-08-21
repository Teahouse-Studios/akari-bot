from copy import deepcopy
from datetime import datetime, UTC
from urllib.parse import urlparse

import orjson
from tortoise import fields
from tortoise.transactions import in_transaction

from core.database.base import DBModel
from core.database.models import TargetUnionInfo, UNION_SCOPE_TARGET, union_mutation

table_prefix = "module_wiki_"


def _normalized_authority(api_link: str) -> tuple[str, int | None] | None:
    """提取用于白名单比较的规范化主机与端口，拒绝无主机或非法端口。"""
    parsed = urlparse(api_link)
    if not parsed.hostname:
        return None
    try:
        port = parsed.port
    except ValueError:
        return None
    return parsed.hostname.rstrip(".").casefold(), port


class WikiTargetInfo(DBModel):
    """
    场景内 Wiki 绑定信息表。

    :param union_id: 场景 union ID
    :param api_link: API 链接
    :param interwikis: 自定义 iw 信息
    :param headers: 自定义请求头
    :param prefix: 自定义请求前缀
    """

    union_scope = UNION_SCOPE_TARGET
    union_id = fields.CharField(max_length=512, primary_key=True)
    api_link = fields.CharField(max_length=512, null=True)
    interwikis = fields.JSONField(default={})
    headers = fields.JSONField(default={"accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6"})
    prefix = fields.CharField(max_length=512, null=True)

    class Meta:
        table = f"{table_prefix}target_set_info"

    async def _mutate(self, mutation) -> bool:
        """在 Union 与模块行均存在时，基于数据库中的最新值执行一次定向更新。"""
        async with union_mutation():
            async with in_transaction("default") as connection:
                target = await (
                    TargetUnionInfo.filter(union_id=self.union_id).using_db(connection).select_for_update().first()
                )
                if not target:
                    return False

                current = await (
                    type(self).filter(union_id=self.union_id).using_db(connection).select_for_update().first()
                )
                if not current:
                    return False

                updates = mutation(current)
                if updates is None:
                    return False
                await type(self).filter(union_id=self.union_id).using_db(connection).update(**updates)
                for field_name, value in updates.items():
                    setattr(self, field_name, deepcopy(value))
                return True

    async def add_start_wiki(self, url: str):
        return await self._mutate(lambda _: {"api_link": url})

    async def config_interwikis(self, iw: str, iwlink: str | None = None):
        def mutate(current):
            interwikis = deepcopy(current.interwikis or {})
            if iwlink:
                interwikis[iw] = iwlink
            else:
                interwikis.pop(iw, None)
            return {"interwikis": interwikis}

        return await self._mutate(mutate)

    async def config_headers(self, headers: str | None = None, add: bool = True):
        try:
            parsed_headers = orjson.loads(headers) if headers and add else None
            if parsed_headers is not None and not isinstance(parsed_headers, dict):
                return False

            def mutate(current):
                current_headers = deepcopy(current.headers or {})
                if parsed_headers is not None:
                    current_headers.update(parsed_headers)
                elif headers:
                    current_headers = {key: value for key, value in current_headers.items() if key != headers}
                else:
                    current_headers = {}
                return {"headers": current_headers}

            return await self._mutate(mutate)
        except Exception:
            return False

    async def config_prefix(self, prefix: str | None = None):
        return await self._mutate(lambda _: {"prefix": prefix})


class WikiSiteInfo(DBModel):
    """
    Wiki 站点信息表。

    :param api_link: API 链接
    :param site_info: 站点信息
    :param timestamp: 更新时间
    """

    api_link = fields.CharField(max_length=512, primary_key=True)
    site_info = fields.JSONField(default={})
    timestamp = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = f"{table_prefix}site_info"

    async def update(self, info: dict):
        timestamp = datetime.now(UTC)
        await type(self).update_or_create(
            api_link=self.api_link,
            defaults={"site_info": info, "timestamp": timestamp},
        )
        self.site_info = deepcopy(info)
        self.timestamp = timestamp
        return True

    @classmethod
    async def get_like_this(cls, t: str):
        return await (cls.filter(api_link__contains=t)).first()


class WikiAllowList(DBModel):
    """
    Wiki 白名单列表。

    :param api_link: API 链接
    :param timestamp: 更新时间
    """

    api_link = fields.CharField(max_length=512, primary_key=True)
    timestamp = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = f"{table_prefix}allow_list"

    @classmethod
    async def check(cls, api_link) -> bool:
        authority = _normalized_authority(api_link)
        if authority is None:
            return False
        allow_links = await cls.all().values_list("api_link", flat=True)
        return any(_normalized_authority(link) == authority for link in allow_links)

    @classmethod
    async def add(cls, api_link) -> bool:
        _, created = await cls.get_or_create(api_link=api_link)
        return created

    @classmethod
    async def remove(cls, api_link) -> bool:
        return bool(await cls.filter(api_link=api_link).delete())


class WikiBlockList(DBModel):
    """
    Wiki 黑名单列表。

    :param api_link: API 链接
    :param timestamp: 更新时间
    """

    api_link = fields.CharField(max_length=512, primary_key=True)
    timestamp = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = f"{table_prefix}block_list"

    @classmethod
    async def check(cls, api_link: str) -> bool:
        return await (cls.filter(api_link=api_link)).exists()

    @classmethod
    async def add(cls, api_link) -> bool:
        _, created = await cls.get_or_create(api_link=api_link)
        return created

    @classmethod
    async def remove(cls, api_link) -> bool:
        return bool(await cls.filter(api_link=api_link).delete())


class WikiBotAccountList(DBModel):
    """
    Wiki Bot 账号列表。

    :param api_link: API 链接
    :param bot_account: Bot 账号
    :param bot_password: Bot 密码
    """

    api_link = fields.CharField(max_length=512, primary_key=True)
    bot_account = fields.CharField(max_length=512)
    bot_password = fields.CharField(max_length=512)

    class Meta:
        table = f"{table_prefix}bot_account_list"

    @classmethod
    async def add(cls, api_link: str, bot_account: str, bot_password: str):
        _, created = await cls.get_or_create(
            api_link=api_link,
            defaults={"bot_account": bot_account, "bot_password": bot_password},
        )
        return created

    @classmethod
    async def remove(cls, api_link):
        return bool(await cls.filter(api_link=api_link).delete())
