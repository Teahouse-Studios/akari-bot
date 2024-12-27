from __future__ import annotations

from typing import Union, List

from tortoise.models import Model
from tortoise import fields

from core.constants import default_locale
from core.utils.list import convert2lst


class SenderInfo(Model):
    sender_id = fields.CharField(max_length=512, pk=True)
    blocked = fields.BooleanField(default=False)
    trusted = fields.BooleanField(default=False)
    superuser = fields.BooleanField(default=False)
    warns = fields.IntField(default=0)
    petal = fields.IntField(default=0)
    sender_data = fields.JSONField(default={})

    class Meta:
        table = "sender_info"


class TargetInfo(Model):
    target_id = fields.CharField(max_length=512, pk=True)
    blocked = fields.BooleanField(default=False)
    modules = fields.JSONField(default=[])
    target_data = fields.JSONField(default={})
    custom_admins = fields.JSONField(default=[])
    muted = fields.BooleanField(default=False)
    locale = fields.CharField(max_length=32, default=default_locale)

    class Meta:
        table = "target_info"

    async def config_module(self, module_name: Union[str, list, tuple[str]], enable: bool):
        module_names = convert2lst(module_name)
        for module_name in module_names:
            if enable:
                if module_name not in self.modules:
                    self.modules.append(module_name)
            else:
                if module_name in self.modules:
                    self.modules.remove(module_name)
        self.modules = list(set(self.modules))
        await self.save()
        return True

    async def switch_mute(self):
        self.muted = not self.muted
        await self.save()
        return self.muted

    async def set_data(self, key: str, value):
        self.target_data[key] = value
        await self.save()

    async def edit_attr(self, key: str, value):
        setattr(self, key, value)
        await self.save()

    async def config_custom_admin(self, sender_id: str, enable: bool):
        custom_admins = self.custom_admins
        if enable:
            if sender_id not in custom_admins:
                custom_admins.append(sender_id)
        else:
            if sender_id in custom_admins:
                custom_admins.remove(sender_id)
        await self.save()
        return self.custom_admins

    @staticmethod
    async def get_target_list_by_module(module_names: Union[str, list[str], tuple[str]], id_prefix=None) -> List[TargetInfo]:
        return [x for x in await TargetInfo.filter(modules__contains=convert2lst(module_names), target_id__startswith=id_prefix or "")]


class StoredData(Model):
    stored_key = fields.CharField(max_length=512, pk=True)
    value = fields.JSONField(default={})

    class Meta:
        table = "stored_data"


class AnalyticsData(Model):
    id = fields.IntField(pk=True)
    module_name = fields.CharField(max_length=512)
    module_type = fields.CharField(max_length=512)
    target_id = fields.CharField(max_length=512)
    sender_id = fields.CharField(max_length=512)
    command = fields.TextField()
    timestamp = fields.DatetimeField(auto_now_add=True)
    data = fields.JSONField(default={})

    class Meta:
        table = "analytics_data"


class DBVersion(Model):
    value = fields.CharField(max_length=32, pk=True)

    class Meta:
        table = "database_version"


class UnfriendlyActionRecords(Model):
    id = fields.IntField(pk=True)
    target_id = fields.CharField(max_length=512)
    sender_id = fields.CharField(max_length=512)
    timestamp = fields.DatetimeField(auto_now_add=True)
    action = fields.CharField(max_length=512)
    detail = fields.CharField(max_length=512)

    class Meta:
        table = "unfriendly_actions"


class JobQueuesTable(Model):
    task_id = fields.UUIDField(pk=True)
    target_client = fields.CharField(max_length=512)
    action = fields.CharField(max_length=512)
    args = fields.JSONField(default={})
    status = fields.CharField(max_length=32, default="pending")
    result = fields.JSONField(default={})
    timestamp = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "job_queues_v2"


__all__ = [
    "SenderInfo",
    "TargetInfo",
    "StoredData",
    "AnalyticsData",
    "DBVersion",
    "UnfriendlyActionRecords",
    "JobQueuesTable",
]
