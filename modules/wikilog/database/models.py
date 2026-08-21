from copy import deepcopy

from tortoise import fields
from tortoise.transactions import in_transaction

from core.database.base import DBModel
from core.database.models import TargetUnionInfo, UNION_SCOPE_TARGET, union_mutation

table_prefix = "module_wikilog_"


class WikiLogTargetSetInfo(DBModel):
    union_scope = UNION_SCOPE_TARGET
    union_id = fields.CharField(max_length=512, primary_key=True)
    infos = fields.JSONField(default={})

    class Meta:
        table = f"{table_prefix}target_set_info"

    async def _mutate_infos(self, mutation) -> bool:
        """锁住所属 Union 与模块行后，基于最新的嵌套配置执行修改。"""
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

                infos = deepcopy(current.infos or {})
                if not mutation(infos):
                    return False
                await type(self).filter(union_id=self.union_id).using_db(connection).update(infos=infos)
                self.infos = deepcopy(infos)
                return True

    async def conf_wiki(self, api_link: str, add=False, reset=False):
        def mutate(infos):
            if add or reset:
                if api_link in infos and not reset:
                    return False
                infos[api_link] = {}
                infos[api_link].setdefault("AbuseLog", {"enable": False, "filters": ["*"]})
                infos[api_link].setdefault(
                    "RecentChanges",
                    {"enable": False, "filters": ["*"], "rcshow": ["!bot"]},
                )
                infos[api_link].setdefault("use_bot", False)
                infos[api_link].setdefault("keep_alive", False)
                infos[api_link].setdefault("note", "")
                return True
            if api_link not in infos:
                return False
            del infos[api_link]
            return True

        return await self._mutate_infos(mutate)

    async def conf_log(self, api_link: str, log_name: str, enable=False):
        def mutate(infos):
            if api_link not in infos or log_name not in infos[api_link]:
                return False
            infos[api_link][log_name]["enable"] = enable
            return True

        return await self._mutate_infos(mutate)

    async def set_filters(self, api_link: str, log_name: str, filters: list[str]):
        def mutate(infos):
            if api_link not in infos or log_name not in infos[api_link]:
                return False
            infos[api_link][log_name]["filters"] = list(filters)
            return True

        return await self._mutate_infos(mutate)

    async def get_filters(self, api_link: str, log_name: str):
        infos = self.infos
        if api_link in infos:
            if log_name in infos[api_link]:
                return infos[api_link][log_name].get("filters")
        return []

    async def set_rcshow(self, api_link: str, rcshow: list[str]):
        def mutate(infos):
            if api_link not in infos or "RecentChanges" not in infos[api_link]:
                return False
            infos[api_link]["RecentChanges"]["rcshow"] = list(rcshow)
            return True

        return await self._mutate_infos(mutate)

    async def get_rcshow(self, api_link: str):
        infos = self.infos
        if api_link in infos:
            if "RecentChanges" in infos[api_link]:
                return infos[api_link]["RecentChanges"].get("rcshow")
        return []

    async def set_use_bot(self, api_link: str, use_bot: bool):
        def mutate(infos):
            if api_link not in infos:
                return False
            infos[api_link]["use_bot"] = use_bot
            return True

        return await self._mutate_infos(mutate)

    async def get_use_bot(self, api_link: str):
        infos = self.infos
        if api_link in infos:
            return infos[api_link].get("use_bot")
        return False

    async def set_keep_alive(self, api_link: str, keep_alive: bool):
        def mutate(infos):
            if api_link not in infos:
                return False
            infos[api_link]["keep_alive"] = keep_alive
            return True

        return await self._mutate_infos(mutate)

    async def get_keep_alive(self, api_link: str):
        infos = self.infos
        if api_link in infos:
            return infos[api_link].get("keep_alive")
        return False

    async def conf_note(self, api_link: str, note: str):
        def mutate(infos):
            if api_link not in infos:
                return False
            infos[api_link]["note"] = note
            return True

        return await self._mutate_infos(mutate)

    @classmethod
    async def return_all_data(cls):
        """
        返回全部配置，键为场景 union ID（推送时需展开为该 union 下的全部平台场景 ID）。
        """
        all_data = await cls.all()
        data_d = {x.union_id: x.infos for x in all_data}
        return data_d
