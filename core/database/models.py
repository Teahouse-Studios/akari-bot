from __future__ import annotations

import uuid
from collections import Counter
from datetime import datetime, UTC
from decimal import Decimal
from typing import Any, List, Optional, Union

from tortoise import fields

from core.constants import default_locale
from core.utils.list import convert2lst
from .base import DBModel


class SenderInfo(DBModel):
    """
    用户信息。

    :param sender_id: 用户 ID。
    :param blocked: 是否为黑名单用户。
    :param trusted: 是否为白名单用户。
    :param superuser: 是否为超级用户。
    :param warns: 用户警告次数。
    :param petal: 用户花瓣数量。
    :param sender_data: 用户数据。
    """

    sender_id = fields.CharField(max_length=512, pk=True)
    blocked = fields.BooleanField(default=False)
    trusted = fields.BooleanField(default=False)
    superuser = fields.BooleanField(default=False)
    warns = fields.IntField(default=0)
    petal = fields.IntField(default=0)
    sender_data = fields.JSONField(default={})

    class Meta:
        table = "sender_info"

    async def switch_identity(self, trust: bool, enable: bool = True) -> bool:
        """
        修改用户身份。

        :param trust: 是否为白名单模式，若 False 则为黑名单模式。
        :param enable: 是否要加入身份，若 False 则取消身份。
        """
        if enable:
            self.trusted = trust
            self.blocked = not trust
        else:
            self.trusted = False
            self.blocked = False

        await self.save()
        return True

    async def warn_user(self, amount: int = 1) -> bool:
        """
        警告用户。

        :param amount: 警告用户次数。
        """
        self.warns = self.warns + amount
        await self.save()
        return True

    async def modify_petal(self, amount: Union[str, int, Decimal]) -> bool:
        """
        修改用户花瓣数量。

        :param amount: 要添加或减少的花瓣数量。
        """
        petal = self.petal + int(amount)
        self.petal = petal
        await self.save()
        return True

    async def clear_petal(self) -> bool:
        """
        清空用户花瓣数量。
        """
        self.petal = 0
        await self.save()
        return True

    async def edit_sender_data(self, key: str, value: Optional[Any]) -> bool:
        """
        设置用户数据。

        :param key: 键名。
        :param value: 值，若留空则删除该键值对。
        """
        if not value:
            if key in self.sender_data:
                del self.sender_data[key]
        else:
            self.sender_data[key] = value

        await self.save()
        return True

    async def edit_attr(self, key: str, value: Any) -> bool:
        setattr(self, key, value)
        await self.save()
        return True


class TargetInfo(DBModel):
    """
    会话信息。

    :param target_id: 会话 ID。
    :param blocked: 是否为黑名单会话。
    :param muted: 是否禁用机器人。
    :param locale: 会话语言。
    :param modules: 会话内可用模块。
    :param custom_admins: 会话内自定义管理员列表。
    :param target_data: 会话数据。
    """
    target_id = fields.CharField(max_length=512, pk=True)
    blocked = fields.BooleanField(default=False)
    muted = fields.BooleanField(default=False)
    locale = fields.CharField(max_length=32, default=default_locale)
    modules = fields.JSONField(default=[])
    custom_admins = fields.JSONField(default=[])
    target_data = fields.JSONField(default={})

    class Meta:
        table = "target_info"

    async def config_module(self, module_name: Union[str, list, tuple[str]], enable: bool = True) -> bool:
        """
        设置会话内可用模块。

        :param module_name: 指定的模块名称。
        :param enable: 是否要开启模块，若 False 则关闭模块。
        """
        module_names = convert2lst(module_name)
        for mname in module_names:
            if enable:
                if mname not in self.modules:
                    self.modules += module_names
            else:
                if mname in self.modules:
                    self.modules += module_names
        await self.save()
        return True

    async def switch_mute(self) -> bool:
        """
        切换是否在会话中禁用机器人。

        :return: 机器人是否被禁用。
        """
        self.muted = not self.muted
        await self.save()
        return self.muted

    async def edit_target_data(self, key: str, value: Optional[Any]) -> bool:
        """
        设置会话数据。

        :param key: 键名。
        :param value: 值，若留空则删除该键值对。
        """
        if not value:
            if key in self.target_data:
                del self.target_data[key]
        else:
            self.target_data[key] = value

        await self.save()
        return True

    async def config_custom_admin(self, sender_id: str, enable: bool = True) -> bool:
        """
        设置会话内管理员。

        :param sender_id: 指定的用户 ID。
        :param enable: 是否要设置用户为会话内管理员，若 False 则移除管理员。
        """
        custom_admins = self.custom_admins
        if enable:
            if sender_id not in custom_admins:
                custom_admins.append(sender_id)
        else:
            if sender_id in custom_admins:
                custom_admins.remove(sender_id)
        await self.save()
        return True

    @classmethod
    async def get_target_list_by_module(cls, module_name: Union[str, list[str], tuple[str]], id_prefix: Optional[str] = None) -> List[TargetInfo]:
        """
        获取开启此模块的所有会话列表。

        :param module_name: 指定的模块名称。
        :param id_prefix: 指定的 ID 前缀。
        :return: 符合要求的会话 ID 列表。
        """
        return list(await cls.filter(modules__contains=convert2lst(module_name), target_id__startswith=id_prefix or ""))

    async def edit_attr(self, key: str, value: Any) -> bool:
        setattr(self, key, value)
        await self.save()
        return True


class StoredData(DBModel):
    """
    数据存储。

    :param stored_key: 存储键。
    :param value: 值。
    """
    stored_key = fields.CharField(max_length=512, pk=True)
    value = fields.JSONField(default=[])

    class Meta:
        table = "stored_data"


class AnalyticsData(DBModel):
    """
    统计数据。

    :param module_name: 模块名称。
    :param module_type: 模块类型。
    :param target_id: 会话 ID。
    :param sender_id: 用户 ID。
    :param command: 命令。
    :param timestamp: 时间戳。
    """
    id = fields.IntField(pk=True)
    module_name = fields.CharField(max_length=512)
    module_type = fields.CharField(max_length=512)
    target_id = fields.CharField(max_length=512)
    sender_id = fields.CharField(max_length=512)
    command = fields.TextField()
    timestamp = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "analytics_data"

    @classmethod
    async def get_data_by_times(cls, new, old, module_name=None):
        query = cls.filter(timestamp__gte=old, timestamp__lte=new)
        if module_name is not None:
            query = query.filter(module_name=module_name)
        return await query.all()

    @classmethod
    async def get_count_by_times(cls, new, old, module_name=None):
        query = cls.filter(timestamp__gte=old, timestamp__lte=new)
        if module_name is not None:
            query = query.filter(module_name=module_name)
        return await query.count()

    @classmethod
    async def get_modules_count(cls):
        analytics = await cls.all().values("module_name")
        module_counter = Counter([entry["module_name"] for entry in analytics])
        return dict(module_counter)


class DBVersion(DBModel):
    """
    数据库版本。

    :param version: 数据库版本号。
    """

    version = fields.IntField(pk=True)

    class Meta:
        table = "database_version"


class UnfriendlyActionRecords(DBModel):
    """
    不友好行为记录。

    :param target_id: 会话 ID。
    :param sender_id: 用户 ID。
    :param action: 行为类型。
    :param detail: 行为详情。
    :param timestamp: 时间戳。
    """
    id = fields.IntField(pk=True)
    target_id = fields.CharField(max_length=512)
    sender_id = fields.CharField(max_length=512)
    action = fields.CharField(max_length=512)
    detail = fields.CharField(max_length=512)
    timestamp = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "unfriendly_actions"

    @classmethod
    async def check_mute(cls, target_id) -> bool:
        """检查会话的禁言行为记录。

        :return: 如果：
        - 会话在过去 5 天内有超过 5 条记录
        - 会话内某一用户的记录（在过去 1 天内）超过 3 次
        - 会话内的不同用户的记录（在过去 1 天内）有 3 个以上

        则返回 True。
        """
        records = await cls.filter(target_id=target_id, action="mute").all()
        unfriendly_list = [
            record for record in records
            if (datetime.now(UTC) - record.timestamp).total_seconds() < 432000  # 5 days
        ]

        if len(unfriendly_list) > 5:
            return True

        count = {}
        for record in unfriendly_list:
            if (datetime.now(UTC) - record.timestamp).total_seconds() < 86400:  # 1 day
                count[record.sender_id] = count.get(record.sender_id, 0) + 1

        if len(count) >= 3 or any(c >= 3 for c in count.values()):
            return True

        return False


class JobQueuesTable(DBModel):
    """
    任务队列表。

    :param task_id: 任务 ID。
    :param target_client: 目标客户端。
    :param action: 动作。
    :param args: 参数。
    :param status: 任务状态。
    :param result: 任务结果。
    :param timestamp: 时间戳。
    """
    task_id = fields.UUIDField(pk=True)
    target_client = fields.CharField(max_length=512)
    action = fields.CharField(max_length=512)
    args = fields.JSONField(default={})
    status = fields.CharField(max_length=32, default="pending")
    result = fields.JSONField(default={})
    timestamp = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "job_queues"

    @classmethod
    async def add_task(cls, target_client: str, action: str, args: dict) -> str:
        task_id = str(uuid.uuid4())
        await cls.create(
            task_id=task_id,
            target_client=target_client,
            action=action,
            args=args
        )
        return task_id

    async def return_val(self, value, status) -> bool:
        self.result = value
        self.status = status
        await self.save()
        return True

    @classmethod
    async def clear_task(cls, time=43200) -> bool:
        now_timestamp = datetime.now().timestamp()

        queries = await cls.all()
        for q in queries:
            if now_timestamp - q.timestamp.timestamp() > time:
                await q.delete()

        return True

    @classmethod
    async def get_first(cls, target_client: str):
        return await cls.filter(
            target_client=target_client, status="pending"
        ).first()

    @classmethod
    async def get_all(cls, target_client: str):
        return await cls.filter(
            target_client=target_client, status="pending"
        ).all()


__all__ = [
    "SenderInfo",
    "TargetInfo",
    "StoredData",
    "AnalyticsData",
    "DBVersion",
    "UnfriendlyActionRecords",
    "JobQueuesTable"
]
