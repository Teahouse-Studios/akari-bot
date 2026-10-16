"""modules/core 管理员命令集成测试。"""

from unittest.mock import AsyncMock, patch

from core.tester import (
    func_case,
    Tester,
    Contains,
)
from core.tester.mock.session import MockMessageSession


async def _is_native_admin(user_id=None):
    """把被查询的成员一律视为平台原生管理员。"""
    return user_id is not None


@func_case
async def test_admin_list(tester: Tester):
    """admin list 命令测试"""
    await tester.integrate("~admin list", Contains("管理员"), "admin list 应显示管理员信息")
    return tester


@func_case
async def test_admin_add_remove(tester: Tester):
    """admin add/remove 流程测试"""
    await tester.integrate("~admin add TEST|999", Contains("管理员"), "admin add 应提示添加结果")
    await tester.integrate("~admin list", Contains("999"), "admin list 应包含新管理员")
    await tester.integrate("~admin remove TEST|999", Contains("管理员"), "admin remove 应提示移除结果")
    return tester


@func_case
async def test_admin_native_admin(tester: Tester):
    """平台原生管理员不受机器人管理员名单管理。"""
    native = AsyncMock(side_effect=_is_native_admin)
    with patch.object(MockMessageSession, "check_native_permission", new=native):
        await tester.integrate(
            "~admin add TEST|999",
            Contains("无须通过机器人设置"),
            "目标为平台原生管理员时应提示无须设置",
        )
        await tester.integrate(
            "~admin remove TEST|999",
            Contains("无法通过机器人解除"),
            "目标为平台原生管理员时应提示无法解除",
        )
    return tester
