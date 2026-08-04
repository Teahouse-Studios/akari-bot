"""setup list 设置面板集成测试。

集成测试走的是 core/tester/mock/parser.py 的简化解析器，其发送者为超级用户，
故此处只验证三条模板各自匹配到位、面板照常发出；权限分支与按钮排布由
tests/unit/test_setup_panel.py 覆盖。
"""

from core.tester import func_case, Tester, All, Contains, Not


@func_case
async def test_setup_list_both(tester: Tester):
    """setup list 两域同列测试"""
    await tester.integrate("~setup list", Contains("场景设置"), "setup list 应列出场景设置")
    await tester.integrate("~setup list", Contains("用户设置"), "setup list 应一并列出用户设置")
    return tester


@func_case
async def test_setup_list_target(tester: Tester):
    """setup list target 只列场景域测试

    反向断言不可省：list 与 list target 两条模板都能匹配这串输入，靠的是后者命中的
    字面量更多而优先级更高。只断言含有场景设置的话，模板一旦退化到 list，两域全列出来
    也照样通过。
    """
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
