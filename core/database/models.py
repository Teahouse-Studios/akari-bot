from __future__ import annotations

import uuid
from collections import Counter
from datetime import datetime, UTC, timedelta
from decimal import Decimal
from typing import Any, Literal, Self, overload

from tortoise import fields
from tortoise.models import Model
from tortoise.transactions import in_transaction

from core.constants.default import default_locale
from core.utils.func import convert_list
from .base import DBModel, extract_session_id
from ..logger import Logger


UNION_SCOPE_SENDER = "sender"
UNION_SCOPE_TARGET = "target"

# 新建 union ID 的域前缀。升级与转换脚本会将旧数据的平台 ID 直接沿用为 union ID，
# 加上前缀后新生成的 ID 不会与平台 ID 混淆，并可直接区分账号组与场景组。
UNION_ID_PREFIXES = {
    UNION_SCOPE_SENDER: "USID",
    UNION_SCOPE_TARGET: "UTID",
}


def get_table_name(model: type[Model]) -> str:
    """
    获取模型对应的数据表名。
    """
    meta = getattr(model, "Meta", None)
    return getattr(meta, "table", None) or model.__name__


def get_union_module_name(model: type[Model]) -> str:
    """
    获取模块表所属的模块名，用于向用户展示，无法判断时退回表名。
    """
    parts = model.__module__.split(".")
    if len(parts) > 1 and parts[0] == "modules":
        return parts[1]
    return get_table_name(model)


def iter_union_models(scope: str | None = None) -> list[type[Model]]:
    """
    遍历所有以 ``union_id`` 为键的模块表，不含核心表与映射表。

    统计与审计表使用 ``sender_union_id`` / ``target_union_id``，不会被纳入，因此合并 union 时不会篡改历史记录。

    :param scope: 限定 union 域（``sender`` / ``target``）。模块表**必须**以类属性 ``union_scope`` 声明自身所属域，
                  未声明者一律跳过并告警：无从判断表里存的是账号数据还是场景数据，
                  两个域都处理会把用户绑定与场景配置互相搬走，比漏迁一张表更难修复。
    """
    from tortoise import Tortoise

    core_models = {SenderUnionInfo, TargetUnionInfo, SenderUnionBind, TargetUnionBind}
    result = []
    for app in Tortoise.apps.values():
        for model in app.values():
            if model in core_models or model in result:
                continue
            if "union_id" not in getattr(model._meta, "fields_map", {}):
                continue
            model_scope = getattr(model, "union_scope", None)
            if not model_scope:
                Logger.warning(
                    f"Table {get_table_name(model)} is keyed by union_id but declares no union_scope, "
                    "so it is excluded from union merge and backfill. "
                    "Declare union_scope = UNION_SCOPE_SENDER or UNION_SCOPE_TARGET on the model."
                )
                continue
            if scope and model_scope != scope:
                continue
            result.append(model)
    return result


async def collect_union_conflicts(from_union: str, to_union: str, scope: str | None = None) -> list[type[Model]]:
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


async def move_union_rows(model: type[Model], from_union: str, to_union: str) -> None:
    """
    将某张模块表中挂在 ``from_union`` 下的行改挂到 ``to_union``。

    模块表多以 ``union_id`` 作主键，而 Tortoise 不允许通过 ``update()`` 修改主键，
    因此这类表只能复制各列后重建行；``union_id`` 非主键的表直接修改该列即可。

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

    # 删除与重建之间若中断，绑定数据将全部丢失，因此置于同一个事务内。
    # 模块表可能挂在 local 连接上，事务须与表所在的连接一致，不能一律使用 default。
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
    把场景权限列表中对某个用户 union 的引用改写到另一个 union 上。

    ``custom_admins`` / ``banned_users`` 存的是用户 union ID，合并后若不改写，
    管理员身份将会丢失，限制名单也可通过换绑绕过。
    """
    for target in await TargetUnionInfo.all():
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
    使新拆出的用户 union 继承原 union 的场景限制名单，避免通过解绑规避封禁。
    """
    for target in await TargetUnionInfo.all():
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
    for info_model in (SenderUnionInfo, TargetUnionInfo):
        bind_model = info_model.bind_model
        union_ids = set(await info_model.all().values_list("union_id", flat=True))
        # iter_union_models 已按 union_scope 过滤，此处取到的必然是同域的表，
        # 不会把场景 ID 误当作用户 ID 建行。
        for model in iter_union_models(info_model.union_scope):
            union_ids |= set(await model.all().values_list("union_id", flat=True))

        missing = union_ids - set(await bind_model.all().values_list(bind_model.id_field, flat=True))
        if missing:
            await bind_model.bulk_create([bind_model(**{bind_model.id_field: i, "union_id": i}) for i in missing])


def normalize_peer_bots(value: Any) -> dict[str, dict[str, str]]:
    """
    规整机器人互认记录，形如 ``{观察方场景 ID: {对端场景 ID: 对端机器人在观察方平台的账号}}``。

    记录须按「观察方 - 对端」两级存放：机器人账号以观察方所在平台的命名空间记录，
    若扁平存为一个列表，则无法反查某条记录属于哪个场景，解绑时也就无从删除。
    旧版本使用的正是扁平列表，此处一律丢弃，重新执行一次 ``bind auto`` 即可。

    :param value: ``target_data["bots_id"]`` 的原始值。
    """
    if not isinstance(value, dict):
        return {}
    return {
        observer: {peer: bot_id for peer, bot_id in entries.items() if bot_id}
        for observer, entries in value.items()
        if isinstance(entries, dict)
    }


class UnionBind(DBModel):
    """
    平台 ID 与 union 的映射关系基类。

    子类须自行定义作为主键的平台 ID 列，并以类属性 :attr:`id_field` 指明该列的列名。

    此表只回答「这个平台 ID 属于哪个 union」，不承载任何状态。封禁一类的判定一律挂在
    :class:`UnionInfo` 上：union 表示同一个人（或同一个现实场景）的多个身份，
    状态若下放到单个 ID，换用组内另一个 ID 即可绕过。

    :param union_id: 所属 union ID。
    :param bound_at: 绑定时间。
    """

    # 子类中作为主键的平台 ID 列名，供按域泛化的查询与补建逻辑使用
    id_field: str

    union_id = fields.CharField(max_length=512, db_index=True)
    bound_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        abstract = True

    @classmethod
    async def list_ids(cls, union_id: str | list[str] | tuple[str, ...]) -> list[str]:
        """
        将 union ID 展开为其下绑定的全部平台 ID。

        :param union_id: 单个或多个 union ID。
        """
        return list(await cls.filter(union_id__in=convert_list(union_id)).values_list(cls.id_field, flat=True))


class SenderUnionBind(UnionBind):
    """
    用户 ID 与 union 的映射关系。

    :param sender_id: 用户 ID（平台账号）。
    """

    id_field = "sender_id"

    sender_id = fields.CharField(max_length=512, primary_key=True)

    class Meta:
        table = "sender_union_bind"


class TargetUnionBind(UnionBind):
    """
    场景 ID 与 union 的映射关系。

    :param target_id: 场景 ID。
    :param channel_id: 所属消息通道号，同组内同号的场景被视为同一个现实场景。
    """

    id_field = "target_id"

    target_id = fields.CharField(max_length=512, primary_key=True)
    channel_id = fields.IntField(default=1)

    class Meta:
        table = "target_union_bind"

    @classmethod
    async def next_channel_id(cls, union_id: str) -> int:
        """
        取该 union 下一个可用的消息通道号。

        通道号仅在组内有意义（消息去重只发生在组内），因此组内自 1 起顺次递增即可。
        默认每个场景各占一号，即默认互不视为同一条消息通道。

        :param union_id: 场景 union ID。
        """
        channels = await cls.filter(union_id=union_id).values_list("channel_id", flat=True)
        return max(channels) + 1 if channels else 1

    @classmethod
    async def list_channels(cls, union_id: str) -> dict[str, int]:
        """
        取该 union 下「平台场景 ID → 消息通道号」的映射。

        :param union_id: 场景 union ID。
        """
        binds = await cls.filter(union_id=union_id).values_list("target_id", "channel_id")
        return dict(binds)


def new_union_id(scope: str) -> str:
    """
    生成一个新的 union ID，形如 ``USID|8B1F...`` / ``UTID|8B1F...``（UUID4 取大写十六进制）。

    :param scope: union 域（``sender`` / ``target``）。
    """
    return f"{UNION_ID_PREFIXES[scope]}|{uuid.uuid4().hex.upper()}"


class UnionInfo(DBModel):
    """
    以 union ID 为主键的核心信息表基类。

    数据挂载在 union 上而非平台 ID 上，多个平台 ID 可通过对应的 :class:`UnionBind` 子表绑定到同一 union 以共享数据。

    子类须声明所属域 :attr:`union_scope` 与配套的映射表 :attr:`bind_model`。
    """

    # 所属 union 域（``sender`` / ``target``）
    union_scope: str
    # 配套的 ID 映射表
    bind_model: type[UnionBind]

    # 由 resolve_union() 挂上的映射行，非数据库字段。
    # 未经解析直接查询（如 all() / filter()）得到的实例上为 None。
    bind: UnionBind | None = None

    union_id = fields.CharField(max_length=512, primary_key=True)
    # 封禁状态只此一处。union 下的全部平台 ID 共享此行，因而封禁天然对组内所有 ID 生效，
    # 不需要再往映射行上放一份标记——那反而会引出「组封了但某 ID 没封」这类无法自洽的状态。
    blocked = fields.BooleanField(default=False)

    class Meta:
        abstract = True

    @overload
    @classmethod
    async def resolve_union(cls, platform_id: str, create: Literal[True] = True) -> Self: ...

    @overload
    @classmethod
    async def resolve_union(cls, platform_id: str, create: bool) -> Self | None: ...

    @classmethod
    async def resolve_union(cls, platform_id: str, create: bool = True) -> Self | None:
        """
        将平台 ID 解析为其所属的 union 信息，并把映射行挂到 :attr:`bind` 上。

        这是 union 的唯一解析入口；:meth:`DBModel.get_by_target_id` 等按会话取行的方法内部同样走这里。

        只有从未出现过的平台 ID 才会被分配新 union；已有映射行的 ID 永远解析回原组，
        因此被封禁的 ID 无法借由重新解析脱离封禁。

        :param platform_id: 平台账号 ID 或平台场景 ID。
        :param create: 若尚未绑定任何 union，是否新建。
        :return: union 信息，若 create 为 False 且不存在则返回 None。
        """
        bind_model = cls.bind_model
        bind = await bind_model.get_or_none(**{bind_model.id_field: platform_id})
        if not bind:
            # 自愈：允许存在 union_id 与平台 ID 相同、但缺少映射行的历史数据。
            exist = await cls.get_or_none(union_id=platform_id)
            if exist:
                bind = await bind_model.create(**{bind_model.id_field: platform_id}, union_id=platform_id)
            elif create:
                bind = await bind_model.create(
                    **{bind_model.id_field: platform_id}, union_id=new_union_id(cls.union_scope)
                )
            else:
                return None

        union = await cls.get_or_none(union_id=bind.union_id)
        if not union:
            if not create:
                return None
            union = await cls.create(union_id=bind.union_id)

        union.bind = bind
        return union

    async def list_bound_ids(self) -> list[str]:
        """
        获取该 union 下已绑定的全部平台 ID。
        """
        return await self.bind_model.list_ids(self.union_id)

    @overload
    @classmethod
    async def _resolve_session(cls, value: Any, create: Literal[True] = True) -> Self: ...

    @overload
    @classmethod
    async def _resolve_session(cls, value: Any, create: bool) -> Self | None: ...

    @classmethod
    async def _resolve_session(cls, value: Any, create: bool = True) -> Self | None:
        """
        从平台 ID 字符串或会话对象解析出 union 信息，供按会话取行的入口复用。

        :param value: 平台 ID，或 MessageSession / FetchedMessageSession 实例。
        :param create: 若尚未绑定任何 union，是否新建。
        """
        id_field = cls.bind_model.id_field
        platform_id = extract_session_id(value, id_field)
        if not platform_id:
            raise ValueError(
                f"{id_field} must be a str or a MessageSession/FetchedMessageSession instance, "
                "or exports are unavailable."
            )
        return await cls.resolve_union(platform_id, create)

    async def edit_attr(self, key: str, value: Any) -> bool:
        setattr(self, key, value)
        await self.save()
        return True


class SenderUnionInfo(UnionInfo):
    """
    用户信息。

    数据挂载在 union 上而非平台账号上，多个平台账号可通过 :class:`SenderUnionBind` 绑定到同一 union 以共享数据。
    平台账号 ID 与 union 的解析见 :meth:`UnionInfo.resolve_union`。

    :param union_id: 用户 union ID。
    :param blocked: 是否为黑名单用户。
    :param trusted: 是否为白名单用户。
    :param superuser: 是否为超级用户。
    :param warns: 用户警告次数。
    :param petal: 用户花瓣数量。
    :param sender_data: 用户数据。
    """

    union_scope = UNION_SCOPE_SENDER
    bind_model = SenderUnionBind

    trusted = fields.BooleanField(default=False)
    superuser = fields.BooleanField(default=False)
    warns = fields.IntField(default=0)
    petal = fields.IntField(default=0)
    sender_data = fields.JSONField(default={})

    class Meta:
        table = "sender_union_info"

    @overload
    @classmethod
    async def get_by_sender_id(cls, sender_id: Any, create: Literal[True] = True) -> "SenderUnionInfo": ...

    @overload
    @classmethod
    async def get_by_sender_id(cls, sender_id: Any, create: bool) -> "SenderUnionInfo | None": ...

    @classmethod
    async def get_by_sender_id(cls, sender_id: Any, create: bool = True) -> "SenderUnionInfo | None":
        """
        取平台账号所属的 union 行，是 :meth:`UnionInfo.resolve_union` 的会话友好包装：
        额外接受 MessageSession / FetchedMessageSession，从中取出 ``sender_id``。
        """
        return await cls._resolve_session(sender_id, create)

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

    async def unbind_id(self, sender_id: str) -> "SenderUnionInfo | None":
        """
        将一个平台账号从该 union 中拆出，数据留在原 union，该账号从零开始。

        惩罚性状态（封禁、警告次数、场景限制名单）随账号一并转移，避免通过解绑规避处罚。

        :param sender_id: 平台账号 ID。
        :return: 拆出后该账号所属的新 union，若无法解绑则为 None。
        """
        binds = await self.list_bound_ids()
        if sender_id not in binds or len(binds) <= 1:
            return None
        union = await SenderUnionInfo.create(
            union_id=new_union_id(UNION_SCOPE_SENDER), blocked=self.blocked, warns=self.warns
        )
        # 先建新组再改挂映射行，全程不出现「该账号没有映射行」的中间态：
        # 该状态下若中断，下次解析会把这个账号当作从未见过的新账号，另建一个干净的 union，
        # 封禁与警告次数就此清零。union_id 不是主键，单条 UPDATE 即可改挂。
        await SenderUnionBind.filter(sender_id=sender_id).update(union_id=union.union_id)
        await inherit_banned_union_refs(self.union_id, union.union_id)
        return union

    async def merge_union(
        self, other: "SenderUnionInfo", keep_other_tables: set[str] | None = None
    ) -> "SenderUnionInfo | None":
        """
        把两个 union 合并成一个全新的 union，随后删除原有的两个。

        不沿用任何一方的 union ID，以消除合并方向上的歧义：合并之后双方的旧组 ID 一律失效。

        :param other: 参与合并的另一方。
        :param keep_other_tables: 模块表冲突时以 ``other`` 为准的表名集合，其余情况保留自身。
        :return: 合并后的新 union，两侧本就同组时为 None。
        """
        if other.union_id == self.union_id:
            return None

        merged = await SenderUnionInfo.create(
            union_id=new_union_id(UNION_SCOPE_SENDER),
            blocked=self.blocked or other.blocked,
            trusted=self.trusted or other.trusted,
            superuser=self.superuser or other.superuser,
            warns=max(self.warns, other.warns),
            petal=self.petal + other.petal,
            sender_data={**other.sender_data, **self.sender_data},
        )

        # 先按冲突取舍将两侧模块数据归拢至一处，再整体改挂到新组；新组为空，第二步不会再产生冲突。
        await migrate_union_tables(other.union_id, self.union_id, keep_other_tables, scope=UNION_SCOPE_SENDER)
        await migrate_union_tables(self.union_id, merged.union_id, scope=UNION_SCOPE_SENDER)

        for old_union in (self.union_id, other.union_id):
            await rewrite_sender_union_refs(old_union, merged.union_id)
            await SenderUnionBind.filter(union_id=old_union).update(union_id=merged.union_id)

        await self.delete()
        await other.delete()
        return merged


class TargetUnionInfo(UnionInfo):
    """
    场景信息。

    数据挂载在 union 上而非平台场景上，多个平台场景可通过 :class:`TargetUnionBind` 绑定到同一 union 以共享数据。
    平台场景 ID 与 union 的解析见 :meth:`UnionInfo.resolve_union`。

    :param union_id: 场景 union ID。
    :param blocked: 是否为黑名单场景。
    :param muted: 是否禁用机器人。
    :param locale: 场景语言。
    :param modules: 场景内可用模块。
    :param custom_admins: 场景内自定义管理员列表（存 union ID）。
    :param banned_users: 场景内已限制用户（存 union ID）。
    :param target_data: 场景数据。
    """

    union_scope = UNION_SCOPE_TARGET
    bind_model = TargetUnionBind

    muted = fields.BooleanField(default=False)
    locale = fields.CharField(max_length=32, default=default_locale)
    modules = fields.JSONField(default=[])
    custom_admins = fields.JSONField(default=[])
    banned_users = fields.JSONField(default=[])
    target_data = fields.JSONField(default={})

    class Meta:
        table = "target_union_info"

    @overload
    @classmethod
    async def get_by_target_id(cls, target_id: Any, create: Literal[True] = True) -> "TargetUnionInfo": ...

    @overload
    @classmethod
    async def get_by_target_id(cls, target_id: Any, create: bool) -> "TargetUnionInfo | None": ...

    @classmethod
    async def get_by_target_id(cls, target_id: Any, create: bool = True) -> "TargetUnionInfo | None":
        """
        取平台场景所属的 union 行，是 :meth:`UnionInfo.resolve_union` 的会话友好包装：
        额外接受 MessageSession / FetchedMessageSession，从中取出 ``target_id``。
        """
        return await cls._resolve_session(target_id, create)

    def list_peer_bots(self, target_id: str) -> list[str]:
        """
        取某个平台场景眼中、同一个现实场景里其它机器人的账号。

        :param target_id: 观察方的平台场景 ID。
        """
        return list(normalize_peer_bots(self.target_data.get("bots_id")).get(target_id, {}).values())

    async def link_peer_bots(self, links: dict[str, dict[str, str]]) -> None:
        """
        登记机器人互认记录。

        :param links: ``{观察方场景 ID: {对端场景 ID: 对端机器人在观察方平台的账号}}``。
        """
        peers = normalize_peer_bots(self.target_data.get("bots_id"))
        for observer, entries in links.items():
            peers.setdefault(observer, {}).update({peer: bot_id for peer, bot_id in entries.items() if bot_id})
        await self.edit_target_data("bots_id", peers)

    async def forget_peer_bots(self, target_id: str) -> None:
        """
        将某个平台场景从机器人互认记录中完全移除，包含它自身的记录与其它场景对它的记录。

        解绑或变更通道后双方不再对应同一个现实场景，保留记录会使双方持续互相屏蔽；
        而重新配对所用的握手口令正是由机器人发出的命令，屏蔽一旦残留，双方将无法重新建立关联。

        :param target_id: 要移除的平台场景 ID。
        """
        peers = normalize_peer_bots(self.target_data.get("bots_id"))
        peers.pop(target_id, None)
        for entries in peers.values():
            entries.pop(target_id, None)
        await self.edit_target_data("bots_id", {observer: e for observer, e in peers.items() if e})

    async def bind_id(self, target_id: str) -> bool:
        """
        将一个平台场景绑定到该 union。

        :param target_id: 平台场景 ID。
        :return: 是否绑定成功，若该场景已绑定至其他 union 则为 False。
        """
        bind = await TargetUnionBind.get_or_none(target_id=target_id)
        if bind:
            return bind.union_id == self.union_id
        await TargetUnionBind.create(
            target_id=target_id,
            union_id=self.union_id,
            channel_id=await TargetUnionBind.next_channel_id(self.union_id),
        )
        return True

    async def unbind_id(self, target_id: str) -> "TargetUnionInfo | None":
        """
        将一个平台场景从该 union 中拆出，数据留在原 union，该场景从零开始。

        :param target_id: 平台场景 ID。
        :return: 拆出后该场景所属的新 union，若无法解绑则为 None。
        """
        binds = await self.list_bound_ids()
        if target_id not in binds or len(binds) <= 1:
            return None
        # 封禁状态随场景一并转移，避免通过解绑规避处罚。
        union = await TargetUnionInfo.create(
            union_id=new_union_id(UNION_SCOPE_TARGET), blocked=self.blocked, locale=self.locale
        )
        # 先建新组再改挂映射行，全程不出现「该场景没有映射行」的中间态：
        # 该状态下若中断，下次解析会把这个场景当作从未见过的新场景，另建一个干净的 union，
        # 封禁就此清零。新组内只此一个场景，通道号复位为 1。
        await TargetUnionBind.filter(target_id=target_id).update(union_id=union.union_id, channel_id=1)
        # 拆出的场景与原组内的机器人不再对应同一个现实场景，互认记录须一并清除。
        # 新组的 target_data 本为空，只需清理保留的一侧。
        await self.forget_peer_bots(target_id)
        return union

    async def merge_union(
        self, other: "TargetUnionInfo", keep_other_tables: set[str] | None = None
    ) -> "TargetUnionInfo | None":
        """
        把两个 union 合并成一个全新的 union，随后删除原有的两个。

        不沿用任何一方的 union ID，以消除合并方向上的歧义：合并之后双方的旧组 ID 一律失效。

        :param other: 参与合并的另一方。
        :param keep_other_tables: 模块表冲突时以 ``other`` 为准的表名集合，其余情况保留自身。
        :return: 合并后的新 union，两侧本就同组时为 None。
        """
        if other.union_id == self.union_id:
            return None

        # bots_id 为两级结构，随 target_data 浅合并会使 other 一侧的互认记录被整体覆盖，
        # 因此单独取并集。
        peer_bots = normalize_peer_bots(other.target_data.get("bots_id"))
        for observer, entries in normalize_peer_bots(self.target_data.get("bots_id")).items():
            peer_bots.setdefault(observer, {}).update(entries)

        merged = await TargetUnionInfo.create(
            union_id=new_union_id(UNION_SCOPE_TARGET),
            blocked=self.blocked or other.blocked,
            muted=self.muted or other.muted,
            locale=self.locale,
            modules=list(set(self.modules) | set(other.modules)),
            custom_admins=list(set(self.custom_admins) | set(other.custom_admins)),
            banned_users=list(set(self.banned_users) | set(other.banned_users)),
            target_data={**other.target_data, **self.target_data, "bots_id": peer_bots},
        )

        # 先按冲突取舍将两侧模块数据归拢至一处，再整体改挂到新组；新组为空，第二步不会再产生冲突。
        await migrate_union_tables(other.union_id, self.union_id, keep_other_tables, scope=UNION_SCOPE_TARGET)
        await migrate_union_tables(self.union_id, merged.union_id, scope=UNION_SCOPE_TARGET)

        # 自身一侧的通道号保持不变，并入方整体平移：双方均自 1 开始编号，
        # 直接合表会使两个互不相关的场景同为 1 号，进而被误判为同一条消息通道。
        # 平移须按原通道号建立映射，不能逐条分配新号——并入方内部原本同号的场景必须保持同号，
        # 否则已配对的场景会在合并时被拆开。
        await TargetUnionBind.filter(union_id=self.union_id).update(union_id=merged.union_id)
        moved_channels: dict[int, int] = {}
        for bind in await TargetUnionBind.filter(union_id=other.union_id).order_by("bound_at"):
            if bind.channel_id not in moved_channels:
                moved_channels[bind.channel_id] = await TargetUnionBind.next_channel_id(merged.union_id)
            bind.union_id = merged.union_id
            bind.channel_id = moved_channels[bind.channel_id]
            await bind.save()

        await self.delete()
        await other.delete()
        return merged

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
    ) -> list[TargetUnionInfo]:
        """
        获取开启此模块的所有场景列表。

        :param module_name: 指定的模块名称。
        :param id_prefix: 指定的 ID 前缀，按 union 下绑定的平台场景 ID 匹配。
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
        获取开启此模块的所有平台场景 ID 列表。

        与 :meth:`get_target_list_by_module` 的区别在于会把每个 union 展开成其下绑定的全部平台场景 ID，
        用于需要逐个场景推送的情形。

        :param module_name: 指定的模块名称。
        :param id_prefix: 指定的 ID 前缀。
        :return: 符合要求的平台场景 ID 列表。
        """
        unions = await cls.get_target_list_by_module(module_name, id_prefix)
        if not unions:
            return []
        query = TargetUnionBind.filter(union_id__in=[t.union_id for t in unions])
        if id_prefix:
            query = query.filter(target_id__startswith=id_prefix)
        return list(await query.values_list("target_id", flat=True))


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
    # 统计命令按时间区间反复聚合，无索引时每次都是全表扫描
    timestamp = fields.DatetimeField(auto_now_add=True, db_index=True)

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
        """检查场景的禁言行为记录。

        统计按 union 聚合，因此换用同一 union 下的其他账号不会绕过此检查。

        :return: 如果：
        - 场景在过去 5 天内有超过 5 条记录
        - 场景内某一用户的记录（在过去 1 天内）超过 3 次
        - 场景内的不同用户的记录（在过去 1 天内）有 3 个以上

        则返回 True。
        """
        target_union_info = await TargetUnionInfo.resolve_union(target_id, create=False)
        if target_union_info:
            records = await cls.filter(target_union_id=target_union_info.union_id, action="mute").all()
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
        # 每个进程每 100 毫秒按这两列轮询一次，无索引时开销随表内行数线性增长
        indexes = (("target_client", "status"),)

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

    :param id: 记录 ID。
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
