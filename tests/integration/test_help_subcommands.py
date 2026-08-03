"""~help 子命令与模块详情的模板优先级测试。

`help doc` / `help donate` 是字面量模板，与 `help <模块名>` 的占位符模板并存。
字面量命中数更多者优先级更高，故 `~help wiki` 仍会落到模块详情，而非把 wiki 当作
不存在的子命令。这条不变量一旦破了，所有模块的帮助都会失灵。
"""

from core.tester import func_case, Tester, Contains, All, Not


@func_case
async def test_help_link_subcommands(tester: Tester):
    """~help doc / donate 子命令测试"""
    await tester.integrate("~help doc", Contains("http"), "help doc 应给出文档地址")
    await tester.integrate("~help donate", Contains("http"), "help donate 应给出捐赠地址")
    return tester


@func_case
async def test_help_module_detail_still_matches(tester: Tester):
    """~help <模块名> 不被字面量子命令抢走"""
    await tester.integrate(
        "~help wiki",
        All(Not(Contains("文档地址")), Not(Contains("打钱"))),
        "help wiki 应落到模块详情而非链接子命令",
    )
    return tester
