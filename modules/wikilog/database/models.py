from tortoise import fields

from core.database.base import DBModel

table_prefix = "module_wikilog_"


class WikiLogTargetSetInfo(DBModel):
    target_id = fields.CharField(max_length=512, pk=True)
    infos = fields.JSONField(default={})

    class Meta:
        table = f"{table_prefix}target_set_info"

    async def conf_wiki(self, api_link: dict, add=False, reset=False):
        infos = self.infos
        if add or reset:
            if api_link not in infos or reset:
                infos[api_link] = {}
                infos[api_link].setdefault(
                    "AbuseLog", {"enable": False, "filters": ["*"]}
                )
                infos[api_link].setdefault(
                    "RecentChanges",
                    {"enable": False, "filters": ["*"], "rcshow": ["!bot"]},
                )
                infos[api_link].setdefault("use_bot", False)
                infos[api_link].setdefault("keep_alive", False)
                await self.save()
                return True
        else:
            if api_link in infos:
                del infos[api_link]
                await self.save()
                return True
        return False

    async def conf_log(self, api_link: str, log_name: str, enable=False):
        infos = self.infos
        if api_link in infos:
            if log_name in infos[api_link]:
                infos[api_link][log_name]["enable"] = enable
                await self.save()
                return True
        return False

    async def set_filters(
        self, api_link: str, log_name: str, filters: list[str]
    ):
        infos = self.infos
        if api_link in infos:
            if log_name in infos[api_link]:
                infos[api_link][log_name]["filters"] = filters
                await self.save()
                return True
        return False

    async def get_filters(self, api_link: str, log_name: str):
        infos = self.infos
        if api_link in infos:
            if log_name in infos[api_link]:
                return infos[api_link][log_name].get("filters")
        return []

    async def set_rcshow(self, api_link: str, rcshow: str):
        infos = self.infos
        if api_link in infos:
            if "RecentChanges" in infos[api_link]:
                infos[api_link]["RecentChanges"]["rcshow"] = rcshow
                await self.save()
                return True
        return False

    async def get_rcshow(self, api_link: str):
        infos = self.infos
        if api_link in infos:
            if "RecentChanges" in infos[api_link]:
                return infos[api_link]["RecentChanges"].get("rcshow")
        return []

    async def set_use_bot(self, api_link: str, use_bot: bool):
        infos = self.infos
        if api_link in infos:
            infos[api_link]["use_bot"] = use_bot
            await self.save()
            return True
        return False

    async def get_use_bot(self, api_link: str):
        infos = self.infos
        if api_link in infos:
            return infos[api_link].get("use_bot")
        return False

    async def set_keep_alive(self, api_link: str, keep_alive: bool):
        infos = self.infos
        if api_link in infos:
            infos[api_link]["keep_alive"] = keep_alive
            await self.save()
            return True
        return False

    async def get_keep_alive(self, api_link: str):
        infos = self.infos
        if api_link in infos:
            return infos[api_link].get("keep_alive")
        return False

    @classmethod
    async def return_all_data(cls):
        all_data = await cls.all()
        data_d = {x.target_id: x.infos for x in all_data}
        return data_d
