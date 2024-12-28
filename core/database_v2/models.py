from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any, List, Optional, Union

import orjson as json
from tortoise.models import Model
from tortoise import fields

from core.constants import default_locale
from core.utils.list import convert2lst
from core.utils.text import isint


class SenderInfo(Model):
    sender_id = fields.CharField(max_length=512, primary_key=True)
    blocked = fields.BooleanField(default=False)
    trusted = fields.BooleanField(default=False)
    superuser = fields.BooleanField(default=False)
    warns = fields.IntField(default=0)
    petal = fields.IntField(default=0)
    sender_data = fields.JSONField(default={})

    class Meta:
        table = "sender_info"

    async def modify_petal(self, amount: Union[str, int, Decimal], absolute: bool) -> bool:
        '''
        修改用户花瓣数量。

        :param amount: 要修改的花瓣数量。
        :param absolute: 是否为绝对模式，若为 True 则覆盖原数值，否则从原数值加上修改数量。
        '''
        petal = self.petal
        if not isint(amount):
            amount = Decimal(amount).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        if absolute:
            petal = int(amount)
        else:
            petal = petal + int(amount)
        petal = 0 if petal < 0 else petal
        self.petal = petal
        await self.save()
        return True

    async def edit_attr(self, key: str, value: Any) -> bool:
        setattr(self, key, value)
        await self.save()
        return True


class TargetInfo(Model):
    target_id = fields.CharField(max_length=512, primary_key=True)
    blocked = fields.BooleanField(default=False)
    modules = fields.JSONField(default=[])
    target_data = fields.JSONField(default={})
    custom_admins = fields.JSONField(default=[])
    muted = fields.BooleanField(default=False)
    locale = fields.CharField(max_length=32, default=default_locale)

    class Meta:
        table = "target_info"

    async def config_module(self, module_name: Union[str, list, tuple[str]], enable: bool) -> bool:
        '''
        设置会话内可用模块。

        :param module_name: 指定的模块名称。
        :param enable: 是否要开启模块，若 False 则关闭模块。
        '''
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

    async def switch_mute(self) -> bool:
        '''
        切换是否在会话中禁用机器人。

        :return: 机器人是否被禁用。
        '''
        self.muted = not self.muted
        await self.save()
        return self.muted

    async def edit_target_data(self, key: str, value: Optional[Any]) -> bool:
        '''
        设置会话数据。

        :param key: 键名。
        :param value: 值，若留空则删除该键值对。
        '''
        target_data = json.loads(self.target_data)

        if not value:
            if key in target_data:
                del target_data[key]
        else:
            target_data[key] = value

        self.target_data = json.dumps(target_data)
        await self.save()
        return True

    async def config_custom_admin(self, sender_id: str, enable: bool) -> bool:
        '''
        设置会话内管理员。

        :param sender_id: 指定的用户 ID。
        :param enable: 是否要设置用户为会话内管理员，若 False 则移除管理员。
        '''
        custom_admins = self.custom_admins
        if enable:
            if sender_id not in custom_admins:
                custom_admins.append(sender_id)
        else:
            if sender_id in custom_admins:
                custom_admins.remove(sender_id)
        await self.save()
        return True

    async def config_target_block(self, enable: bool) -> bool:
        '''
        设置是否将会话加入黑名单。

        :param enable: 是否要加入黑名单，若 False 则移除黑名单。
        '''
        self.blocked = enable
        await self.save()
        return True

    @staticmethod
    async def get_target_list_by_module(module_names: Union[str, list[str], tuple[str]],
                                        id_prefix: Optional[str] = None) -> List[TargetInfo]:
        '''
        获取开启此模块的所有会话列表。

        :param module_names: 指定的模块名称。
        :param id_prefix: 指定的 ID 前缀。
        :return: 符合要求的会话 ID 列表。
        '''
        return [x for x in await TargetInfo.filter(modules__contains=convert2lst(module_names),
                                                   target_id__startswith=id_prefix or "")]

    async def edit_attr(self, key: str, value: Any) -> bool:
        setattr(self, key, value)
        await self.save()
        return True


class StoredData(Model):
    stored_key = fields.CharField(max_length=512, primary_key=True)
    value = fields.JSONField(default={})

    class Meta:
        table = "stored_data"


class AnalyticsData(Model):
    id = fields.IntField(primary_key=True)
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
    value = fields.CharField(max_length=32, primary_key=True)

    class Meta:
        table = "database_version"


class UnfriendlyActionRecords(Model):
    id = fields.IntField(primary_key=True)
    target_id = fields.CharField(max_length=512)
    sender_id = fields.CharField(max_length=512)
    timestamp = fields.DatetimeField(auto_now_add=True)
    action = fields.CharField(max_length=512)
    detail = fields.CharField(max_length=512)

    class Meta:
        table = "unfriendly_actions"


class JobQueuesTable(Model):
    task_id = fields.UUIDField(primary_key=True)
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
