from __future__ import annotations

import uuid
from collections import Counter
from datetime import datetime, UTC, timedelta
from decimal import Decimal
from typing import Any

from tortoise import fields
from tortoise.transactions import in_transaction

from core.constants.default import default_locale
from core.utils.func import convert_list
from .base import DBModel
from ..logger import Logger


UNION_SCOPE_SENDER = "sender"
UNION_SCOPE_TARGET = "target"

# 新建 union ID 的域前缀。升级与转换脚本会把旧数据的平台 ID 原样当作 union ID 沿用，
# 加上前缀后新生成的 ID 不会与平台 ID 混淆，也能一眼看出是账号组还是会话组。
UNION_ID_PREFIXES = {
    UNION_SCOPE_SENDER: "USID",
    UNION_SCOPE_TARGET: "UTID",
}


def get_table_name(model: type) -> str:
    """
    获取模型对应的数据表名。
    """
    meta = getattr(model, "Meta", None)
    return getattr(meta, "table", None) or model.__name__


def get_union_module_name(model: type) -> str:
    """
    获取模块表所属的模块名，用于向用户展示，无法判断时退回表名。
    """
    parts = model.__module__.split(".")
    if len(parts) > 1 and parts[0] == "modules":
        return parts[1]
    return get_table_name(model)


def iter_union_models(scope: str | None = None) -> list[type]:
    """
    遍历所有以 ``union_id`` 为键的模块表，不含核心表与映射表。

    统计与审计表使用 ``sender_union_id`` / ``target_union_id``，不会被纳入，因此合并 union 时不会篡改历史记录。

    :param scope: 限定 union 域（``sender`` / ``target``）。模块表以类属性 ``union_scope`` 声明自身所属域，
                  未声明的表在两个域中都会被处理，以免合并后残留无人认领的数据。
    """
    from tortoise import Tortoise

    core_models = {SenderInfo, TargetInfo, SenderUnionBind, TargetUnionBind}
    result = []
    for app in Tortoise.apps.values():
        for model in app.values():
            if model in core_models or model in result:
                continue
            if "union_id" not in getattr(model._meta, "fields_map", {}):
                continue
            model_scope = getattr(model, "union_scope", None)
            if scope and model_scope and model_scope != scope:
                continue
            result.append(model)
    return result


async def collect_union_conflicts(from_union: str, to_union: str, scope: str | None = None) -> list[type]:
    """
    列出两个 union 在模块表上互相冲突（双方都有数据）的模型。

    :param from_union: 来源 union ID。
    :param to_union: 目标 union ID。
    :param scope: 限定 union 域。
    """
    conflicts = []
    for model in iter_union_models(scope):
        if await model.filter(union_id=from_union).exists() and await model.filter(union_id=to_union).exists():
            conflicts.append(model)
    return conflicts


async def move_union_rows(model: type, from_union: str, to_union: str) -> None:
    """
    将某张模块表中挂在 ``from_union`` 下的行改挂到 ``to_union``。

    模块表多以 ``union_id`` 作主键，而 Tortoise 不允许用 ``update()`` 改主键，
    因此这类表只能照抄各列后重建行；``union_id`` 不是主键的表直接改列即可。

    :param model: 模块表模型。
    :param from_union: 来源 union ID。
    :param to_union: 目标 union ID。
    """
    if model._meta.pk_attr != "union_id":
        await model.filter(union_id=from_union).update(union_id=to_union)
        return

    rows = await model.filter(union_id=from_union)
    if not rows:
        return

    columns = list(model._meta.fields_db_projection)
    moved = []
    for row in rows:
        data = {column: getattr(row, column) for column in columns}
        data["union_id"] = to_union
        moved.append(model(**data))

    # 删除与重建之间若中断，绑定数据会凭空消失，因此放进同一个事务。
    # 模块表可能挂在 local 连接上，事务要跟着表走，不能一律用 default。
    async with in_transaction(model._meta.default_connection):
        await model.filter(union_id=from_union).delete()
        await model.bulk_create(moved)


async def migrate_union_tables(
    from_union: str,
    to_union: str,
    keep_other_tables: set[str] | None = None,
    scope: str | None = None,
) -> None:
    """
    将模块表中挂在 ``from_union`` 下的数据迁移到 ``to_union``。

    :param from_union: 来源 union ID。
    :param to_union: 目标 union ID。
    :param keep_other_tables: 冲突时以来源方为准的表名集合，其余情况保留目标方。
    :param scope: 限定 union 域。
    """
    keep_other_tables = keep_other_tables or set()
    for model in iter_union_models(scope):
        if not await model.filter(union_id=from_union).exists():
            continue
        if await model.filter(union_id=to_union).exists():
            if get_table_name(model) in keep_other_tables:
                await model.filter(union_id=to_union).delete()
            else:
                await model.filter(union_id=from_union).delete()
                continue
        await move_union_rows(model, from_union, to_union)


async def rewrite_sender_union_refs(from_union: str, to_union: str) -> None:
    """
    把会话权限列表中对某个用户 union 的引用改写到另一个 union 上。

    ``custom_admins`` / ``banned_users`` 存的是用户 union ID，合并后若不改写，
    管理员身份会凭空消失，限制名单也能被换绑绕过。
    """
    for target in await TargetInfo.all():
        changed = False
        for field in ("custom_admins", "banned_users"):
            value = getattr(target, field) or []
            if from_union in value:
                setattr(target, field, list(dict.fromkeys(to_union if v == from_union else v for v in value)))
                changed = True
        if changed:
            await target.save()


async def inherit_banned_union_refs(from_union: str, to_union: str) -> None:
    """
    让新拆出的用户 union 继承原 union 的会话限制名单，避免通过解绑洗掉封禁。
    """
    for target in await TargetInfo.all():
        banned_users = target.banned_users or []
        if from_union in banned_users and to_union not in banned_users:
            target.banned_users = banned_users + [to_union]
            await target.save()


async def backfill_union_binds() -> None:
    """
    为缺少映射行的 union 补建 ID 映射。

    升级与转换脚本沿用「union ID 即原平台 ID」的约定，因此这里把核心表与模块表中出现过的 union ID
    直接当作平台 ID 建立映射。模块表可能引用核心表里没有的 ID（旧版本的模块绑定不会顺带建用户行），
    这些 ID 同样要补上映射，否则下次解析会另建一个空 union，模块绑定就此悬空。
    """
    for info_model, bind_model, id_field, scope in (
        (SenderInfo, SenderUnionBind, "sender_id", UNION_SCOPE_SENDER),
        (TargetInfo, TargetUnionBind, "target_id", UNION_SCOPE_TARGET),
    ):
        union_ids = set(await info_model.all().values_list("union_id", flat=True))
        for model in iter_union_models(scope):
            # 仅采纳明确声明了所属域的模块表，避免把场景 ID 误当作用户 ID 建行。
            if getattr(model, "union_scope", None) != scope:
                continue
            union_ids |= set(await model.all().values_list("union_id", flat=True))

        missing = union_ids - set(await bind_model.all().values_list(id_field, flat=True))
        if missing:
            await bind_model.bulk_create([bind_model(**{id_field: i, "union_id": i}) for i in missing])


def attach_bind(union: Any, bind: Any) -> Any:
    """
    将映射行挂到 union 实例上，并把账号级封禁合成到 union 的 ``blocked`` 上。

    合成结果只存在于内存中，用于实现「union 下任一账号被封则整体视为封禁」。
    """
    union._bind = bind
    if bind.blocked:
        union.blocked = True
    return union


class SenderUnionBind(DBModel):
    """
    用户 ID 与 union 的映射关系。

    :param sender_id: 用户 ID（平台账号）。
    :param union_id: 所属 union ID。
    :param blocked: 该账号是否被单独封禁。
    :param bound_at: 绑定时间。
    """

    sender_id = fields.CharField(max_length=512, primary_key=True)
    union_id = fields.CharField(max_length=512, db_index=True)
    blocked = fields.BooleanField(default=False)
    bound_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "sender_union_bind"


class TargetUnionBind(DBModel):
    """
    场景 ID 与 union 的映射关系。

    :param target_id: 场景 ID（平台会话）。
    :param union_id: 所属 union ID。
    :param blocked: 该场景是否被单独封禁。
    :param bound_at: 绑定时间。
    """

    target_id = fields.CharField(max_length=512, primary_key=True)
    union_id = fields.CharField(max_length=512, db_index=True)
    blocked = fields.BooleanField(default=False)
    bound_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "target_union_bind"


def new_union_id(scope: str) -> str:
    """
    生成一个新的 union ID，形如 ``USID|8B1F...`` / ``UTID|8B1F...``（UUID4 取大写十六进制）。

    :param scope: union 域（``sender`` / ``target``）。
    """
    return f"{UNION_ID_PREFIXES[scope]}|{uuid.uuid4().hex.upper()}"


class SenderInfo(DBModel):
    """
    用户信息。

    数据挂载在 union 上而非平台账号上，多个平台账号可通过 :class:`SenderUnionBind` 绑定到同一 union 以共享数据。

    :param union_id: 用户 union ID。
    :param blocked: 是否为黑名单用户。
    :param trusted: 是否为白名单用户。
    :param superuser: 是否为超级用户。
    :param warns: 用户警告次数。
    :param petal: 用户花瓣数量。
    :param sender_data: 用户数据。
    """

    union_id = fields.CharField(max_length=512, primary_key=True)
    blocked = fields.BooleanField(default=False)
    trusted = fields.BooleanField(default=False)
    superuser = fields.BooleanField(default=False)
    warns = fields.IntField(default=0)
    petal = fields.IntField(default=0)
    sender_data = fields.JSONField(default={})

    class Meta:
        table = "sender_info"

    @classmethod
    async def resolve_union(cls, sender_id: str, create: bool = True) -> "SenderInfo | None":
        """
        将平台账号 ID 解析为其所属的 union 信息。

        :param sender_id: 平台账号 ID。
        :param create: 若尚未绑定任何 union，是否新建。
        :return: union 信息，若 create 为 False 且不存在则返回 None。
        """
        bind = await SenderUnionBind.get_or_none(sender_id=sender_id)
        if not bind:
            # 自愈：允许存在 union_id 与 sender_id 相同、但缺少映射行的历史数据。
            exist = await cls.get_or_none(union_id=sender_id)
            if exist:
                bind = await SenderUnionBind.create(sender_id=sender_id, union_id=sender_id, blocked=exist.blocked)
            elif create:
                bind = await SenderUnionBind.create(sender_id=sender_id, union_id=new_union_id(UNION_SCOPE_SENDER))
            else:
                return None

        union = await cls.get_or_none(union_id=bind.union_id)
        if not union:
            if not create:
                return None
            union = await cls.create(union_id=bind.union_id)

        return attach_bind(union, bind)

    async def list_bound_ids(self) -> list[str]:
        """
        获取该 union 下已绑定的全部平台账号 ID。
        """
        return await self.list_ids_by_union(self.union_id)

    @staticmethod
    async def list_ids_by_union(union_id: str | list[str] | tuple[str, ...]) -> list[str]:
        """
        将 union ID 展开为其下绑定的全部平台账号 ID。

        :param union_id: 单个或多个 union ID。
        """
        return list(
            await SenderUnionBind.filter(union_id__in=convert_list(union_id)).values_list("sender_id", flat=True)
        )

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
        if not self.blocked:
            # 解封时同时清除账号级封禁，否则下次解析仍会被合成为封禁状态。
            await SenderUnionBind.filter(union_id=self.union_id).update(blocked=False)
            if bind := getattr(self, "_bind", None):
                bind.blocked = False
        return True

    async def warn_user(self, amount: int = 1) -> bool:
        """
        警告用户。

        :param amount: 警告用户次数。
        """
        self.warns = self.warns + amount
        await self.save()
        return True

    async def modify_petal(self, amount: str | int | Decimal) -> bool:
        """
        修改用户花瓣数量。

        :param amount: 要添加或减少的花瓣数量。
        """
        self.petal += int(amount)
        await self.save()
        return True

    async def clear_petal(self) -> bool:
        """
        清空用户花瓣数量。
        """
        self.petal = 0
        await self.save()
        return True

    async def edit_sender_data(self, key: str, value: Any | None = None) -> bool:
        """
        设置用户数据。

        :param key: 键名。
        :param value: 值，若留空则删除该键值对。
        """
        if value is None:
            if key in self.sender_data:
                del self.sender_data[key]
        else:
            self.sender_data[key] = value

        await self.save()
        return True

    async def edit_attr(self, key: str, value: Any) -> bool:
        setattr(self, key, value)
        await self.save()
        if key == "blocked" and not value:
            # 解封时同时清除账号级封禁，否则下次解析仍会被合成为封禁状态。
            await SenderUnionBind.filter(union_id=self.union_id).update(blocked=False)
            if bind := getattr(self, "_bind", None):
                bind.blocked = False
        return True

    async def bind_id(self, sender_id: str) -> bool:
        """
        将一个平台账号绑定到该 union。

        :param sender_id: 平台账号 ID。
        :return: 是否绑定成功，若该账号已绑定至其他 union 则为 False。
        """
        bind = await SenderUnionBind.get_or_none(sender_id=sender_id)
        if bind:
            return bind.union_id == self.union_id
        await SenderUnionBind.create(sender_id=sender_id, union_id=self.union_id)
        return True

    async def unbind_id(self, sender_id: str) -> "SenderInfo | None":
        """
        将一个平台账号从该 union 中拆出，数据留在原 union，该账号从零开始。

        惩罚性状态（封禁、警告次数、会话限制名单）会随账号一并带走，避免通过解绑洗掉处罚。

        :param sender_id: 平台账号 ID。
        :return: 拆出后该账号所属的新 union，若无法解绑则为 None。
        """
        binds = await self.list_bound_ids()
        if sender_id not in binds or len(binds) <= 1:
            return None
        bind = await SenderUnionBind.get_or_none(sender_id=sender_id)
        blocked = self.blocked or (bind.blocked if bind else False)
        await SenderUnionBind.filter(sender_id=sender_id).delete()
        union = await SenderInfo.create(union_id=new_union_id(UNION_SCOPE_SENDER), blocked=blocked, warns=self.warns)
        await SenderUnionBind.create(sender_id=sender_id, union_id=union.union_id, blocked=blocked)
        await inherit_banned_union_refs(self.union_id, union.union_id)
        return union

    async def merge_union(self, other: "SenderInfo", keep_other_tables: set[str] | None = None) -> bool:
        """
        将另一 union 并入该 union，随后删除被并入的 union。

        :param other: 被并入的 union。
        :param keep_other_tables: 模块表冲突时以被并入方为准的表名集合，其余情况保留自身。
        """
        if other.union_id == self.union_id:
            return False

        self.petal += other.petal
        self.warns = max(self.warns, other.warns)
        self.blocked = self.blocked or other.blocked
        self.trusted = self.trusted or other.trusted
        self.superuser = self.superuser or other.superuser
        self.sender_data = {**other.sender_data, **self.sender_data}
        await self.save()

        await migrate_union_tables(other.union_id, self.union_id, keep_other_tables, scope=UNION_SCOPE_SENDER)
        await rewrite_sender_union_refs(other.union_id, self.union_id)
        await SenderUnionBind.filter(union_id=other.union_id).update(union_id=self.union_id)
        await other.delete()
        return True


class TargetInfo(DBModel):
    """
    场景信息。

    数据挂载在 union 上而非平台会话上，多个平台会话可通过 :class:`TargetUnionBind` 绑定到同一 union 以共享数据。

    :param union_id: 场景 union ID。
    :param blocked: 是否为黑名单会话。
    :param muted: 是否禁用机器人。
    :param locale: 会话语言。
    :param modules: 会话内可用模块。
    :param custom_admins: 会话内自定义管理员列表（存 union ID）。
    :param banned_users: 会话内已限制用户（存 union ID）。
    :param target_data: 会话数据。
    """

    union_id = fields.CharField(max_length=512, primary_key=True)
    blocked = fields.BooleanField(default=False)
    muted = fields.BooleanField(default=False)
    locale = fields.CharField(max_length=32, default=default_locale)
    modules = fields.JSONField(default=[])
    custom_admins = fields.JSONField(default=[])
    banned_users = fields.JSONField(default=[])
    target_data = fields.JSONField(default={})

    class Meta:
        table = "target_info"

    @classmethod
    async def resolve_union(cls, target_id: str, create: bool = True) -> "TargetInfo | None":
        """
        将平台会话 ID 解析为其所属的 union 信息。

        :param target_id: 平台会话 ID。
        :param create: 若尚未绑定任何 union，是否新建。
        :return: union 信息，若 create 为 False 且不存在则返回 None。
        """
        bind = await TargetUnionBind.get_or_none(target_id=target_id)
        if not bind:
            # 自愈：允许存在 union_id 与 target_id 相同、但缺少映射行的历史数据。
            exist = await cls.get_or_none(union_id=target_id)
            if exist:
                bind = await TargetUnionBind.create(target_id=target_id, union_id=target_id, blocked=exist.blocked)
            elif create:
                bind = await TargetUnionBind.create(target_id=target_id, union_id=new_union_id(UNION_SCOPE_TARGET))
            else:
                return None

        union = await cls.get_or_none(union_id=bind.union_id)
        if not union:
            if not create:
                return None
            union = await cls.create(union_id=bind.union_id)

        return attach_bind(union, bind)

    async def list_bound_ids(self) -> list[str]:
        """
        获取该 union 下已绑定的全部平台会话 ID。
        """
        return await self.list_ids_by_union(self.union_id)

    @staticmethod
    async def list_ids_by_union(union_id: str | list[str] | tuple[str, ...]) -> list[str]:
        """
        将 union ID 展开为其下绑定的全部平台会话 ID。

        :param union_id: 单个或多个 union ID。
        """
        return list(
            await TargetUnionBind.filter(union_id__in=convert_list(union_id)).values_list("target_id", flat=True)
        )

    async def bind_id(self, target_id: str) -> bool:
        """
        将一个平台会话绑定到该 union。

        :param target_id: 平台会话 ID。
        :return: 是否绑定成功，若该会话已绑定至其他 union 则为 False。
        """
        bind = await TargetUnionBind.get_or_none(target_id=target_id)
        if bind:
            return bind.union_id == self.union_id
        await TargetUnionBind.create(target_id=target_id, union_id=self.union_id)
        return True

    async def unbind_id(self, target_id: str) -> "TargetInfo | None":
        """
        将一个平台会话从该 union 中拆出，数据留在原 union，该会话从零开始。

        :param target_id: 平台会话 ID。
        :return: 拆出后该会话所属的新 union，若无法解绑则为 None。
        """
        binds = await self.list_bound_ids()
        if target_id not in binds or len(binds) <= 1:
            return None
        bind = await TargetUnionBind.get_or_none(target_id=target_id)
        blocked = self.blocked or (bind.blocked if bind else False)
        await TargetUnionBind.filter(target_id=target_id).delete()
        # 封禁状态随会话一并带走，避免通过解绑洗掉处罚。
        union = await TargetInfo.create(union_id=new_union_id(UNION_SCOPE_TARGET), blocked=blocked, locale=self.locale)
        await TargetUnionBind.create(target_id=target_id, union_id=union.union_id, blocked=blocked)
        return union

    async def merge_union(self, other: "TargetInfo", keep_other_tables: set[str] | None = None) -> bool:
        """
        将另一 union 并入该 union，随后删除被并入的 union。

        :param other: 被并入的 union。
        :param keep_other_tables: 模块表冲突时以被并入方为准的表名集合，其余情况保留自身。
        """
        if other.union_id == self.union_id:
            return False

        self.blocked = self.blocked or other.blocked
        self.muted = self.muted or other.muted
        self.modules = list(set(self.modules) | set(other.modules))
        self.custom_admins = list(set(self.custom_admins) | set(other.custom_admins))
        self.banned_users = list(set(self.banned_users) | set(other.banned_users))
        self.target_data = {**other.target_data, **self.target_data}
        await self.save()

        await migrate_union_tables(other.union_id, self.union_id, keep_other_tables, scope=UNION_SCOPE_TARGET)
        await TargetUnionBind.filter(union_id=other.union_id).update(union_id=self.union_id)
        await other.delete()
        return True

    async def config_module(self, module_name: str | list | tuple, enable: bool = True) -> bool:
        """
        设置场景内可用模块。

        :param module_name: 指定的模块名称。
        :param enable: 是否要开启模块，若 False 则关闭模块。
        """
        module_names = convert_list(module_name)
        for mname in module_names:
            if enable:
                if mname not in self.modules:
                    self.modules.append(mname)
            else:
                if mname in self.modules:
                    self.modules.remove(mname)
        self.modules = list(set(self.modules))
        await self.save()
        return True

    async def switch_mute(self) -> bool:
        """
        切换是否在场景中禁用机器人。

        :return: 机器人是否被禁用。
        """
        self.muted = not self.muted
        await self.save()
        return self.muted

    async def edit_target_data(self, key: str, value: Any | None = None) -> bool:
        """
        设置场景数据。

        :param key: 键名。
        :param value: 值，若留空则删除该键值对。
        """
        if value is None:
            if key in self.target_data:
                del self.target_data[key]
        else:
            self.target_data[key] = value

        await self.save()
        return True

    async def config_custom_admin(self, sender_union_id: str, enable: bool = True) -> bool:
        """
        设置场景内管理员。

        :param sender_union_id: 指定的用户 union ID。
        :param enable: 是否要设置用户为场景内管理员，若 False 则移除管理员。
        """
        custom_admins = self.custom_admins
        if enable:
            if sender_union_id not in custom_admins:
                custom_admins.append(sender_union_id)
            else:
                return False
        elif sender_union_id in custom_admins:
            custom_admins.remove(sender_union_id)

        self.custom_admins = custom_admins
        await self.save()
        return True

    async def config_banned_user(self, sender_union_id: str, enable: bool = True) -> bool:
        """
        设置场景内被限制用户。

        :param sender_union_id: 指定的用户 union ID。
        :param enable: 是否要设置场景内用户限制使用机器人，若 False 则取消限制。
        """
        banned_users = self.banned_users
        if enable:
            if sender_union_id not in banned_users:
                banned_users.append(sender_union_id)
            else:
                return False
        else:
            if sender_union_id in banned_users:
                banned_users.remove(sender_union_id)
            else:
                return False

        self.banned_users = banned_users
        await self.save()
        return True

    @classmethod
    async def get_target_list_by_module(
        cls, module_name: str | list[str] | tuple[str, ...] | None, id_prefix: str | None = None
    ) -> list[TargetInfo]:
        """
        获取开启此模块的所有场景列表。

        :param module_name: 指定的模块名称。
        :param id_prefix: 指定的 ID 前缀，按 union 下绑定的平台会话 ID 匹配。
        :return: 符合要求的场景 union 列表。
        """
        if id_prefix:
            union_ids = await TargetUnionBind.filter(target_id__startswith=id_prefix).values_list("union_id", flat=True)
            all_targets = await cls.filter(union_id__in=list(set(union_ids)))
        else:
            all_targets = await cls.all()

        if module_name:
            result = []
            for target in all_targets:
                modules = target.modules or []
                if any(mod in modules for mod in convert_list(module_name)):
                    result.append(target)
            return result

        return list(all_targets)

    @classmethod
    async def get_target_id_list_by_module(
        cls, module_name: str | list[str] | tuple[str, ...] | None, id_prefix: str | None = None
    ) -> list[str]:
        """
        获取开启此模块的所有平台会话 ID 列表。

        与 :meth:`get_target_list_by_module` 的区别在于会把每个 union 展开成其下绑定的全部平台会话 ID，
        用于需要逐个会话推送的场景。

        :param module_name: 指定的模块名称。
        :param id_prefix: 指定的 ID 前缀。
        :return: 符合要求的平台会话 ID 列表。
        """
        unions = await cls.get_target_list_by_module(module_name, id_prefix)
        if not unions:
            return []
        query = TargetUnionBind.filter(union_id__in=[t.union_id for t in unions])
        if id_prefix:
            query = query.filter(target_id__startswith=id_prefix)
        return list(await query.values_list("target_id", flat=True))

    async def edit_attr(self, key: str, value: Any) -> bool:
        setattr(self, key, value)
        await self.save()
        if key == "blocked" and not value:
            # 解封时同时清除会话级封禁，否则下次解析仍会被合成为封禁状态。
            await TargetUnionBind.filter(union_id=self.union_id).update(blocked=False)
            if bind := getattr(self, "_bind", None):
                bind.blocked = False
        return True


class StoredData(DBModel):
    """
    数据存储。

    :param stored_key: 存储键。
    :param value: 值。
    """

    stored_key = fields.CharField(max_length=512, primary_key=True)
    value = fields.JSONField(default=[])

    class Meta:
        table = "stored_data"


class AnalyticsData(DBModel):
    """
    统计数据。

    :param module_name: 模块名称。
    :param module_type: 模块类型。
    :param target_id: 场景 ID。
    :param sender_id: 用户 ID。
    :param target_union_id: 场景所属 union ID。
    :param sender_union_id: 用户所属 union ID。
    :param command: 命令。
    :param timestamp: 时间戳。
    """

    id = fields.IntField(primary_key=True)
    module_name = fields.CharField(max_length=512)
    module_type = fields.CharField(max_length=512)
    target_id = fields.CharField(max_length=512)
    sender_id = fields.CharField(max_length=512, null=True, default=None)
    target_union_id = fields.CharField(max_length=512, null=True, default=None)
    sender_union_id = fields.CharField(max_length=512, null=True, default=None)
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
    async def get_values_by_times(cls, new, old, module_name=None):
        query = cls.filter(timestamp__gte=old, timestamp__lte=new)
        if module_name is not None:
            query = query.filter(module_name=module_name)
        return await query.values()

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


class ModuleStatus(DBModel):
    """
    模块状态。

    :param module_name: 模块名称。
    :param load: 是否已加载。
    """

    module_name = fields.CharField(primary_key=True, max_length=255, unique=True)
    load = fields.BooleanField(default=False)

    class Meta:
        table = "module_status"

    @classmethod
    async def init_modules(cls, modules_list: list[str]):
        async with in_transaction("default"):
            existing = await cls.all().values_list("module_name", flat=True)
            existing_set = set(existing)
            input_set = set(modules_list)

            to_add = input_set.difference(existing_set)
            to_remove = existing_set.difference(input_set)

            if to_add:
                await cls.bulk_create([cls(module_name=m, load=True) for m in to_add])

            if to_remove:
                await cls.filter(module_name__in=to_remove).delete()

    @classmethod
    async def set_module_loaded(cls, module_name: str, load: bool = True):
        module = await cls.filter(module_name=module_name).first()
        if module:
            module.load = load
            await module.save()
        else:
            raise ValueError(f"Module '{module_name}' not found")

    @classmethod
    async def get_all_modules(cls) -> list[str]:
        return await cls.all().values_list("module_name", flat=True)

    @classmethod
    async def get_loaded_modules(cls) -> list[str]:
        return await cls.filter(load=True).values_list("module_name", flat=True)

    @classmethod
    async def get_unloaded_modules(cls) -> list[str]:
        return await cls.filter(load=False).values_list("module_name", flat=True)


class DBVersion(DBModel):
    """
    数据库版本。

    :param version: 数据库版本号。
    """

    version = fields.IntField(primary_key=True)

    class Meta:
        table = "database_version"


class UnfriendlyActionRecords(DBModel):
    """
    不友好行为记录。

    :param target_id: 场景 ID。
    :param sender_id: 用户 ID。
    :param target_union_id: 场景所属 union ID。
    :param sender_union_id: 用户所属 union ID。
    :param action: 行为类型。
    :param detail: 行为详情。
    :param timestamp: 时间戳。
    """

    id = fields.IntField(primary_key=True)
    target_id = fields.CharField(max_length=512)
    sender_id = fields.CharField(max_length=512)
    target_union_id = fields.CharField(max_length=512, null=True, default=None)
    sender_union_id = fields.CharField(max_length=512, null=True, default=None)
    action = fields.CharField(max_length=512)
    detail = fields.CharField(max_length=512)
    timestamp = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "unfriendly_actions"

    @classmethod
    async def check_mute(cls, target_id) -> bool:
        """检查会话的禁言行为记录。

        统计按 union 聚合，因此换用同一 union 下的其他账号不会绕过此检查。

        :return: 如果：
        - 会话在过去 5 天内有超过 5 条记录
        - 会话内某一用户的记录（在过去 1 天内）超过 3 次
        - 会话内的不同用户的记录（在过去 1 天内）有 3 个以上

        则返回 True。
        """
        target_info = await TargetInfo.resolve_union(target_id, create=False)
        if target_info:
            records = await cls.filter(target_union_id=target_info.union_id, action="mute").all()
        else:
            records = await cls.filter(target_id=target_id, action="mute").all()
        unfriendly_list = [
            record
            for record in records
            if (datetime.now(UTC) - record.timestamp).total_seconds() < 432000  # 5 days
        ]

        if len(unfriendly_list) > 5:
            return True

        count = {}
        for record in unfriendly_list:
            if (datetime.now(UTC) - record.timestamp).total_seconds() < 86400:  # 1 day
                key = record.sender_union_id or record.sender_id
                count[key] = count.get(key, 0) + 1

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

    task_id = fields.UUIDField(primary_key=True)
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
        await cls.create(task_id=task_id, target_client=target_client, action=action, args=args)
        return task_id

    async def set_val(self, value, status) -> bool:
        self.result = value
        self.status = status
        await self.save()
        return True

    async def set_status(self, status):
        self.status = status
        await self.save()
        return True

    @classmethod
    async def clear_task(cls, time=3600) -> bool:
        timestamp = datetime.now(UTC) - timedelta(seconds=time)
        Logger.debug(f"Clearing tasks older than {timestamp}...")

        await cls.filter(timestamp__lt=timestamp).delete()
        return True

    @classmethod
    async def get_first(cls, target_clients: str | list[str]):
        if isinstance(target_clients, str):
            target_clients = [target_clients]
        return await cls.filter(target_client__in=target_clients, status="pending").first()

    @classmethod
    async def get_all(cls, target_clients: str | list[str]):
        if isinstance(target_clients, str):
            target_clients = [target_clients]
        return await cls.filter(target_client__in=target_clients, status="pending").all()


class MaliciousLoginRecords(DBModel):
    """
    恶意登录行为记录。

    :param id: 会话 ID。
    :param ip_address: IP 地址。
    :param blocked_until: 被封禁的截止时间。
    :param created_date: 创建日期。
    """

    id = fields.IntField(primary_key=True)
    ip_address = fields.CharField(max_length=45)
    blocked_until = fields.DatetimeField()
    created_date = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "malicious_login"

    @classmethod
    async def check_blocked(cls, ip_address: str) -> bool:
        return await cls.filter(ip_address=ip_address, blocked_until__gt=datetime.now(UTC)).exists()
