"""nintendo-err 结果转 Embed 的单元测试。"""

from core.builtins.message.elements import EmbedElement
from core.tester import func_case, Tester
from modules.nintendo_err import Results, _build_embed

SWITCH_CODE = "2160-0007"


def _test_switch_code_returns_result():
    results = Results()
    ret = results.fetch(results.fixup_input(SWITCH_CODE))
    return ret is not None and bool(ret.get_title())


def _test_embed_carries_title_and_fields():
    results = Results()
    ret = results.fetch(results.fixup_input(SWITCH_CODE))
    embed = _build_embed(ret)
    expected = [(field.field_name, field.message, False) for field in ret]
    actual = [(field.name, field.value, field.inline) for field in embed.fields]
    return isinstance(embed, EmbedElement) and embed.title == ret.get_title() and actual == expected and bool(actual)


def _test_embed_description_matches_result():
    results = Results()
    ret = results.fetch(results.fixup_input(SWITCH_CODE))
    return _build_embed(ret).description == ret.extra_description


@func_case
async def test_nintendo_err_embed(tester: Tester):
    """nintendo-err: 结果对象转换为 Embed 时不再经过平台 SDK"""
    await tester.test(_test_switch_code_returns_result, "Switch 错误码可查询")
    await tester.test(_test_embed_carries_title_and_fields, "标题与字段完整转换")
    await tester.test(_test_embed_description_matches_result, "描述与结果对象一致")
    return tester
