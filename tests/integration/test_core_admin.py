"""modules/core 管理员命令集成测试。"""

from core.tester import (
    func_case,
    Tester,
    Contains,
)


@func_case
async def test_admin_list(tester: Tester):
    """admin list 命令测试"""
    await tester.expect("~admin list", Contains("管理员"), "admin list 应显示管理员信息")
    return tester


@func_case
async def test_admin_add_remove(tester: Tester):
    """admin add/remove 流程测试"""
    await tester.expect("~admin add TEST|999", Contains("管理员"), "admin add 应提示添加结果")
    await tester.expect("~admin list", Contains("999"), "admin list 应包含新管理员")
    await tester.expect("~admin remove TEST|999", Contains("管理员"), "admin remove 应提示移除结果")
    return tester


@func_case
async def test_admin_permission(tester: Tester):
    """admin 命令权限测试"""
    await tester.expect("~admin list", Contains("管理员"), "admin list 应可被普通用户执行")
    return tester
