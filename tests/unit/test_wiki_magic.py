import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import PlainElement, URLElement
from core.builtins.session.info import SessionInfo
from core.builtins.session.internal import MessageSession
from core.constants.exceptions import SessionFinished
from core.i18n import Locale
from core.tester import Tester, func_case
from modules.wiki.utils.magic import (
    MagicRegistry,
    MagicWordError,
    _REGISTRY_CACHE,
    expand_magic,
    extract_expressions,
    get_registry,
)
from modules.wiki.utils.wikilib import InvalidWikiError, WikiInfo, WikiLib
from modules.wiki.wiki import query_expressions

API = "https://example.org/api.php"


def _metadata():
    return {
        "query": {
            "variables": ["sitename", "currentyear", "pagename", "revisionid", "numberofarticles"],
            "functionhooks": [
                "expr",
                "if",
                "ifeq",
                "switch",
                "pagename",
                "fullurl",
                "urlencode",
                "anchorencode",
                "formatnum",
                "urldecode",
                "invoke",
                "padleft",
            ],
            "magicwords": [
                {"name": "sitename", "aliases": ["SITENAME", "站点名称"], "case-sensitive": ""},
                {"name": "currentyear", "aliases": ["CURRENTYEAR"], "case-sensitive": True},
                {"name": "pagename", "aliases": ["PAGENAME", "页名"], "case-sensitive": True},
                {"name": "revisionid", "aliases": ["REVISIONID"], "case-sensitive": True},
                {"name": "numberofarticles", "aliases": ["NUMBEROFARTICLES"], "case-sensitive": True},
                {"name": "expr", "aliases": ["expr", "计算式"], "case-sensitive": False},
                {"name": "if", "aliases": ["if", "如果"]},
                {"name": "ifeq", "aliases": ["ifeq"]},
                {"name": "switch", "aliases": ["switch"]},
                {"name": "fullurl", "aliases": ["FULLURL:", "完整URL:"]},
                {"name": "urlencode", "aliases": ["URLENCODE:"]},
                {"name": "anchorencode", "aliases": ["ANCHORENCODE", "锚编码"]},
                {"name": "formatnum", "aliases": ["FORMATNUM", "格式化数字"]},
                {"name": "urldecode", "aliases": ["urldecode", "URI解碼"]},
                {"name": "invoke", "aliases": ["invoke"]},
                {"name": "padleft", "aliases": ["PADLEFT:"]},
            ],
        }
    }


def _registry():
    return MagicRegistry(_metadata()["query"], {"Template", "模板"})


def _wiki(api=API):
    wiki = WikiLib(api)
    wiki.wiki_info = WikiInfo(
        api=api,
        realurl="https://example.org",
        articlepath="https://example.org/wiki/$1",
        script="https://example.org/index.php",
        namespaces={"Template": 10, "模板": 10},
        is_allowed=True,
    )
    return wiki


def _node(text):
    return extract_expressions(text)[0]


def _test_aliases_and_template_conflicts():
    registry = _registry()
    for source, name in [
        ("{{SITENAME}}", "sitename"),
        ("{{站点名称}}", "sitename"),
        ("{{#计算式:2+2}}", "expr"),
        ("{{#EXPR:2+2}}", "expr"),
        ("{{完整URL:石头}}", "fullurl"),
        ("{{锚编码:Some section}}", "anchorencode"),
        ("{{FORMATNUM:1000}}", "formatnum"),
        ("{{#URI解碼:%41}}", "urldecode"),
    ]:
        assert registry.lookup(_node(source)).name == name
    for source in ["{{sitename}}", "{{Infobox|x=1}}", "{{Template:SITENAME}}", "{{模板:SITENAME}}", "{{FULLURL}}"]:
        assert registry.lookup(_node(source)) is None
    return True


def _test_outer_expressions_and_ignored_markup():
    text = "A {{#if:1|{{#expr:2+2}}|0}} B {{Infobox|name={{SITENAME}}}}"
    assert [str(node) for node in extract_expressions(text)] == [
        "{{#if:1|{{#expr:2+2}}|0}}",
        "{{Infobox|name={{SITENAME}}}}",
    ]
    for source in [
        "{{broken|{{SITENAME}}",
        "{{{x|{{SITENAME}}}}}",
        "<!-- {{SITENAME}} -->",
        "<nowiki>{{SITENAME}}</nowiki>",
        "<code>{{SITENAME}}</code>",
    ]:
        assert not extract_expressions(source), source
    return True


def _test_validation_and_context():
    registry = _registry()
    assert registry.validate("{{#if:1|{{#expr:2+2}}|0}}", None).name == "if"
    assert registry.validate("{{PAGENAME:Template:Info}}", None).name == "pagename"
    assert registry.validate("{{页名}}", "Help:Some page").needs_page
    cases = [
        ("{{PAGENAME}}", "page_required"),
        ("{{PAGENAME:}}", "page_required"),
        ("{{#invoke:Module|run}}", "unsupported"),
        ("{{PADLEFT:foo|10000000}}", "unsupported"),
        ("{{#if:1|{{Infobox}}|0}}", "unsupported"),
        ("{{#if:1|{{:Article}}|0}}", "unsupported"),
        ("{{#if:1|{{{x}}}|0}}", "unsupported"),
        ("{{#if:1|<b>Text</b>|0}}", "unsupported"),
        ("{{REVISIONID}}", "unsupported"),
        ("{{#unknown:1}}", "unsupported"),
        ("{{SITENAME}} {{CURRENTYEAR}}", "invalid"),
        ("{{#expr:2+2}", "invalid"),
        ("{{#if:1|" + "x" * 400 + "|0}}", "input_long"),
        ("{{#if:1|" * 6 + "x" + "|0}}" * 6, "input_long"),
    ]
    for source, key in cases:
        try:
            registry.validate(source, None)
        except MagicWordError as error:
            assert error.key.endswith("." + key), source
        else:
            raise AssertionError(source)
    return True


async def _test_registry_cache_and_invalid_response():
    _REGISTRY_CACHE.clear()
    wiki = _wiki()
    wiki.get_json = AsyncMock(return_value=_metadata())
    first = await get_registry(wiki)
    assert await get_registry(wiki) is first and wiki.get_json.await_count == 1
    other = _wiki("https://other.org/api.php")
    other.get_json = AsyncMock(return_value=_metadata())
    assert await get_registry(other) is not first and other.get_json.await_count == 1
    _REGISTRY_CACHE[API].ts -= 43201
    assert await get_registry(wiki) is not first and wiki.get_json.await_count == 2
    _REGISTRY_CACHE.clear()
    wiki.get_json = AsyncMock(side_effect=[{}, _metadata()])
    try:
        await get_registry(wiki)
    except InvalidWikiError:
        pass
    else:
        return False
    assert isinstance(await get_registry(wiki), MagicRegistry) and wiki.get_json.await_count == 2
    _REGISTRY_CACHE.clear()
    return True


async def _test_expand_values_and_context():
    wiki = _wiki()
    wiki.get_json = AsyncMock(return_value={"expandtemplates": {"wikitext": "10"}})
    assert await expand_magic(wiki, _registry(), "{{#expr:2*3+4}}") == ("10", False)
    assert wiki.get_json.await_args.kwargs == {
        "action": "expandtemplates",
        "text": "{{#expr:2*3+4}}",
        "prop": "wikitext",
    }
    wiki.get_json = AsyncMock(return_value={"expandtemplates": {"wikitext": "Some page"}})
    assert await expand_magic(wiki, _registry(), "{{PAGENAME}}", "Help:Some page") == ("Some page", False)
    assert wiki.get_json.await_args.kwargs["title"] == "Help:Some page"
    wiki.get_json = AsyncMock(return_value={"expandtemplates": {"wikitext": "//example.org/wiki/Stone"}})
    assert await expand_magic(wiki, _registry(), "{{fullurl:Stone}}") == ("https://example.org/wiki/Stone", True)
    return True


async def _test_expansion_errors_and_bounds():
    cases = [
        ({"expandtemplates": {"wikitext": "<strong class='error'>Division by zero</strong>"}}, "evaluation_failed"),
        ({"expandtemplates": {"wikitext": "[[:Template:Missing]]"}}, "not_plain"),
        ({"expandtemplates": {"wikitext": "<table>Content</table>"}}, "not_plain"),
        ({"expandtemplates": {"wikitext": "x" * 201}}, "output_long"),
        ({"expandtemplates": {"wikitext": "1\n2\n3\n4"}}, "output_long"),
        ({"expandtemplates": {"wikitext": "10"}, "warnings": {"expandtemplates": "Bad title"}}, "context_failed"),
    ]
    wiki = _wiki()
    for response, key in cases:
        wiki.get_json = AsyncMock(return_value=response)
        try:
            await expand_magic(wiki, _registry(), "{{#expr:1/0}}")
        except MagicWordError as error:
            assert error.key.endswith("." + key)
        else:
            return False
    wiki.get_json = AsyncMock(
        return_value={"expandtemplates": {"wikitext": "https://example.org/index.php?action=edit"}}
    )
    try:
        await expand_magic(wiki, _registry(), "{{fullurl:Stone}}")
    except MagicWordError as error:
        assert error.key.endswith(".read_only_url")
    else:
        return False
    for response in ({"expandtemplates": {"wikitext": None}}, {"expandtemplates": None}, {}):
        wiki.get_json = AsyncMock(return_value=response)
        try:
            await expand_magic(wiki, _registry(), "{{SITENAME}}")
        except InvalidWikiError:
            pass
        else:
            return False
    wiki.get_json = AsyncMock(return_value={"expandtemplates": {"wikitext": ""}})
    assert await expand_magic(wiki, _registry(), "{{#if:|A|}}") == ("", False)
    wiki.get_json = AsyncMock()
    try:
        await expand_magic(wiki, _registry(), "{{#if:1|{{#invoke:Module|run}}|}}")
    except MagicWordError:
        assert not wiki.get_json.await_count
    else:
        return False
    return True


async def _test_cancellation_is_not_swallowed():
    wiki = _wiki()
    wiki.get_json = AsyncMock(side_effect=asyncio.CancelledError)
    try:
        await expand_magic(wiki, _registry(), "{{SITENAME}}")
    except asyncio.CancelledError:
        return True
    return False


async def _route(
    text, *, magic_only=False, inline=False, page=None, registry=None, value="10", is_url=False, registry_error=None
):
    session = MessageSession(
        session_info=SessionInfo(
            target_id="TEST|Group|magic",
            target_from="TEST|Group",
            client_name="TEST",
            sender_id="TEST|1",
            locale=Locale("zh_cn"),
        )
    )
    captured = {}

    async def finish(self, chain=None, **_):
        captured["messages"] = MessageChain.assign(chain)
        raise SessionFinished

    target = SimpleNamespace(api_link=API, headers={}, prefix="Configured:")

    async def prepare(wiki):
        wiki.wiki_info = _wiki().wiki_info
        if registry_error:
            raise registry_error
        return registry or _registry()

    with (
        patch("modules.wiki.wiki.WikiTargetInfo.get_by_target_id", new=AsyncMock(return_value=target)),
        patch("modules.wiki.wiki.finish_if_wiki_blocked", new=AsyncMock()),
        patch("modules.wiki.wiki.get_registry", new=prepare),
        patch("modules.wiki.wiki.expand_magic", new=AsyncMock(return_value=(value, is_url))) as expand,
        patch("modules.wiki.wiki.query_pages", new=AsyncMock()) as templates,
        patch.object(MessageSession, "finish", new=finish),
    ):
        try:
            await query_expressions(session, text, magic_only=magic_only, inline=inline, page=page)
        except SessionFinished:
            pass
    return captured, expand, templates, session


async def _test_routing_templates_and_magic():
    messages, expand, templates, _ = await _route("{{Infobox|name={{SITENAME}}}}", inline=True)
    assert not expand.await_count and not messages
    assert templates.await_args.args[1] == ["Infobox"]
    messages, expand, templates, _ = await _route("{{模板:SITENAME}}")
    assert not expand.await_count and templates.await_args.args[1] == ["SITENAME"]
    messages, expand, templates, _ = await _route("{{站点名称}}")
    assert expand.await_count == 1 and not templates.await_count and messages["messages"].to_str() == "10"
    messages, expand, templates, _ = await _route("{{Infobox}} {{#expr:1+1}}", inline=True)
    assert expand.await_count == 1 and templates.await_args.kwargs["preset_message"].to_str() == "10"
    return True


async def _test_explicit_shorthand_and_context():
    messages, expand, templates, _ = await _route("#expr:2*3+4", magic_only=True)
    assert expand.await_args.args[2] == "{{#expr:2*3+4}}" and not templates.await_count
    _, expand, _, _ = await _route("{{PAGENAME}}", magic_only=True, page="Help:Some page")
    assert expand.await_args.args[3] == "Help:Some page"
    return True


async def _test_output_is_literal_and_url_policy():
    payload = "[KE:image,path=https://example.org/remote.png] {I18N:message.success}"
    captured, _, _, session = await _route("{{#if:1|Text|}}", value=payload)
    chain = captured["messages"]
    assert isinstance(chain.values[0], PlainElement) and not chain.values[0].allow_parse
    rendered = chain.as_sendable(session.session_info)
    assert len(rendered) == 1 and isinstance(rendered.values[0], PlainElement) and rendered.values[0].text == payload
    captured, _, _, _ = await _route("{{fullurl:Other}}", value="https://other.org/wiki/Other", is_url=True)
    assert isinstance(captured["messages"].values[0], URLElement)
    assert captured["messages"].values[0].trusted is None
    return True


async def _test_inline_batch_limit_and_registry_failure():
    captured, expand, _, _ = await _route("{{SITENAME}} {{CURRENTYEAR}} {{#expr:1+1}} {{#expr:2+2}}", inline=True)
    assert expand.await_count == 3 and len(captured["messages"]) == 3
    assert all(isinstance(item, PlainElement) and not item.allow_parse for item in captured["messages"])
    assert captured["messages"].values[0].text == "SITENAME = 10"
    _, expand, templates, _ = await _route("{{Infobox}}", inline=True, registry_error=InvalidWikiError("Unavailable"))
    assert not expand.await_count and templates.await_args.args[1] == ["Infobox"]
    captured, expand, templates, _ = await _route("{{SITENAME}}", registry_error=InvalidWikiError("Unavailable"))
    assert not expand.await_count and not templates.await_count
    assert captured["messages"].values[0].key == "wiki.message.magic.unavailable"
    return True


@func_case
async def test_wiki_magic(tester: Tester):
    for function, note in [
        (_test_aliases_and_template_conflicts, "站点别名、大小写与显式模板命名空间识别"),
        (_test_outer_expressions_and_ignored_markup, "仅识别外层表达式，忽略注释、代码和参数占位符"),
        (_test_validation_and_context, "限制嵌套与普通模板展开，页面变量要求上下文"),
        (_test_registry_cache_and_invalid_response, "能力缓存按 API 隔离，过期和异常响应重新请求"),
        (_test_expand_values_and_context, "只读展开传递完整表达式与页面上下文，生成绝对链接"),
        (_test_expansion_errors_and_bounds, "区分求值错误、复杂与长结果、空值及无效响应"),
        (_test_cancellation_is_not_swallowed, "求值取消正确传播"),
        (_test_routing_templates_and_magic, "普通模板保持文档查询，魔术字和混合消息正确分流"),
        (_test_explicit_shorthand_and_context, "显式入口支持短写表达式和页面上下文"),
        (_test_output_is_literal_and_url_policy, "结果不解析消息标记，外站链接保持 URL 策略"),
        (_test_inline_batch_limit_and_registry_failure, "内联结果合并限量，能力发现失败保留普通模板查询"),
    ]:
        await tester.test(function, note)
    return tester
