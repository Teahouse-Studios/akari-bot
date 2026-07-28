"""更多工具模块集成测试 - nbnhhsh、idlist。

nbnhhsh 与 idlist 的响应均由 tests/fixtures/http/ 下的录制内容提供，断言可以直接
针对固定语料，不受线上词库变动影响。nbnhhsh 以 POST 请求体区分查询词，fixture
按「URL + 方法 + 请求体摘要」匹配，因此同一接口的不同查询各自对应独立语料。
"""

from core.tester import (
    func_case,
    Tester,
    Contains,
)


@func_case
async def test_nbnhhsh(tester: Tester):
    """nbnhhsh 模块测试 - 缩写翻译"""
    await tester.integrate("~nbnhhsh yyds", Contains("永远滴神"), "nbnhhsh 应返回缩写含义")
    return tester


@func_case
async def test_nbnhhsh_multi_segment(tester: Tester):
    """nbnhhsh 多段缩写测试 - 接口会按下划线拆分，模块只取第一段"""
    await tester.integrate(
        "~nbnhhsh abcdefghijk_xyz",
        Contains("A boy can do everything for girl"),
        "nbnhhsh 应返回首段缩写的含义",
    )
    return tester


@func_case
async def test_nbnhhsh_not_found(tester: Tester):
    """nbnhhsh 未找到测试

    线上接口对任意输入都会给出结果，未找到分支无法由真实响应触发，
    故以一份空响应语料覆盖该分支。
    """
    await tester.integrate(
        "~nbnhhsh zzz_no_such_abbr",
        Contains("没有匹配到拼音首字母缩写"),
        "nbnhhsh 空结果应提示未找到",
    )
    return tester


@func_case
async def test_idlist(tester: Tester):
    """idlist 模块测试 - 命令 ID 查询"""
    await tester.integrate("~idlist stone", Contains("stone"), "idlist 应返回匹配结果")
    return tester


@func_case
async def test_idlist_not_found(tester: Tester):
    """idlist 未找到测试"""
    await tester.integrate("~idlist nonexistent_xyz_12345", Contains("没有"), "idlist 未找到应提示")
    return tester
