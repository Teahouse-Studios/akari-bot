"""测试数据工厂 - 快速创建测试数据。"""

from __future__ import annotations

from core.database.models import SenderUnionInfo, TargetUnionInfo


class TestDataFactory:
    """测试数据工厂，用于快速创建数据库测试数据。"""

    @staticmethod
    async def ensure_sender(
        sender_id: str = "TEST|0",
        superuser: bool = True,
        blocked: bool = False,
        trusted: bool = False,
        warns: int = 0,
        petal: int = 0,
        sender_data: dict | None = None,
    ) -> SenderUnionInfo:
        """确保用户数据存在，不存在则创建。

        :param sender_id: 用户 ID
        :param superuser: 是否为超级用户
        :param blocked: 是否被封禁
        :param trusted: 是否被信任
        :param warns: 警告次数
        :param petal: 花瓣数量
        :param sender_data: 自定义数据
        :returns: SenderUnionInfo 实例
        """
        obj = await SenderUnionInfo.resolve_union(sender_id)
        obj.superuser = superuser
        obj.blocked = blocked
        obj.trusted = trusted
        obj.warns = warns
        obj.petal = petal
        obj.sender_data = sender_data or {}
        await obj.save()
        return obj

    @staticmethod
    async def ensure_target(
        target_id: str = "TEST|Console|0",
        blocked: bool = False,
        muted: bool = False,
        locale: str = "zh_cn",
        modules: list[str] | None = None,
        custom_admins: list[str] | None = None,
        banned_users: list[str] | None = None,
        target_data: dict | None = None,
    ) -> TargetUnionInfo:
        """确保场景数据存在，不存在则创建。

        :param target_id: 场景 ID
        :param blocked: 是否被封禁
        :param muted: 是否被禁言
        :param locale: 语言设置
        :param modules: 启用的模块列表
        :param custom_admins: 自定义管理员列表
        :param banned_users: 被封禁用户列表
        :param target_data: 自定义数据
        :returns: TargetUnionInfo 实例
        """
        obj = await TargetUnionInfo.resolve_union(target_id)
        obj.blocked = blocked
        obj.muted = muted
        obj.locale = locale
        obj.modules = modules or []
        obj.custom_admins = custom_admins or []
        obj.banned_users = banned_users or []
        obj.target_data = target_data or {}
        await obj.save()
        return obj

    @staticmethod
    async def setup_default_test_env():
        """设置默认测试环境（创建默认用户和场景）。

        :returns: (sender_union_info, target_union_info) 元组
        """
        sender = await TestDataFactory.ensure_sender()
        target = await TestDataFactory.ensure_target()
        return sender, target

    @staticmethod
    async def setup_superuser_env():
        """设置超级用户测试环境。

        :returns: (sender_union_info, target_union_info) 元组
        """
        sender = await TestDataFactory.ensure_sender(superuser=True)
        target = await TestDataFactory.ensure_target()
        return sender, target

    @staticmethod
    async def setup_normal_user_env():
        """设置普通用户测试环境。

        :returns: (sender_union_info, target_union_info) 元组
        """
        sender = await TestDataFactory.ensure_sender(superuser=False)
        target = await TestDataFactory.ensure_target()
        return sender, target


__all__ = ["TestDataFactory"]
