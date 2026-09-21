"""setup list 设置面板集成测试。"""

from core.tester import func_case, Tester, All, Contains, Not


@func_case
async def test_setup_list_both(tester: Tester):
    """setup list 两域同列测试"""
    await tester.integrate("~setup list", Contains("场景设置"), "setup list 应列出场景设置")
    await tester.integrate("~setup list", Contains("用户设置"), "setup list 应一并列出用户设置")
    return tester


@func_case
async def test_setup_list_target(tester: Tester):
    """setup list target 只列场景域测试"""
    await tester.integrate(
        "~setup list target",
        All(Contains("场景设置"), Contains("时间偏移"), Not(Contains("用户设置"))),
        "setup list target 应只列出场景设置",
    )
    return tester


@func_case
async def test_setup_list_sender(tester: Tester):
    """setup list sender 只列个人域测试"""
    await tester.integrate(
        "~setup list sender",
        All(Contains("用户设置"), Contains("输入提示"), Not(Contains("场景设置"))),
        "setup list sender 应只列出用户设置",
    )
    return tester
