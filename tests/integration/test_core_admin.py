"""modules/core 管理员与模块授权命令集成测试。"""

from unittest.mock import AsyncMock, patch

from core.tester import (
    func_case,
    Tester,
    ActionContains,
    All,
    Contains,
    Not,
)
from core.tester.mock.session import MockMessageSession

STRICT_CONFIRM_TEXT = "我授权用户 TEST|999 使用模块 auth。"


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
            Contains("无须设置机器人管理员权限"),
            "目标为平台原生管理员时应提示无须设置",
        )
        await tester.integrate(
            "~admin remove TEST|999",
            Contains("无法通过机器人解除"),
            "目标为平台原生管理员时应提示无法解除",
        )
    return tester


@func_case
async def test_auth_add_strict_confirmation(tester: Tester):
    """auth add 的高危操作严格确认流程测试"""
    # 测试进程没有平台 Peer，ID 归属校验由 mock 提供
    with patch("modules.core.su_tools.auth.Alive.determine_sender_from", return_value="TEST"):
        await tester.integrate(
            ["~auth add TEST|999 auth", "是", STRICT_CONFIRM_TEXT],
            All(Contains("成功授权"), ActionContains(STRICT_CONFIRM_TEXT)),
            "auth add 应展示确认语句并提示授权结果",
        )
        await tester.integrate("~auth list TEST|999", Contains("授权使用模块"), "auth list 应包含新授权")
        await tester.integrate(["~auth remove TEST|999 auth"], Contains("已取消"), "auth remove 应提示取消结果")
    return tester


@func_case
async def test_auth_add_rejects_wrong_confirmation(tester: Tester):
    """auth add 未完全回复确认语句时不应授权"""
    with patch("modules.core.su_tools.auth.Alive.determine_sender_from", return_value="TEST"):
        await tester.integrate(
            ["~auth add TEST|998 auth", "是", "确认"],
            All(ActionContains("我授权用户 TEST|998 使用模块 auth。"), Not(Contains("成功授权"))),
            "确认语句不符时不应提示授权结果",
        )
        await tester.integrate("~auth list TEST|998", Contains("暂无任何授权记录"), "auth list 应无授权记录")
    return tester
