import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlsplit

from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import (
    ButtonFrameElement,
    I18NContextElement,
    ImageElement,
    PlainElement,
    VideoElement,
)
from core.builtins.message.internal import Image
from core.builtins.session.info import SessionInfo
from core.builtins.session.internal import MessageSession
from core.constants.exceptions import SessionFinished
from core.i18n import Locale
from core.tester import Tester, func_case
from modules.wiki.inline import _parse_wiki_urls, _read_url_page
from modules.wiki.search import search_pages
from modules.wiki.utils.media import file_preview
from modules.wiki.utils.wikilib import InvalidWikiError, PageInfo, WikiAPIError, WikiInfo, WikiLib, WikiStatus
from modules.wiki.wiki import _build_section_callback, query_pages

API = "https://example.org/w/api.php"
ARTICLE = "https://example.org/wiki/$1"
SCRIPT = "https://example.org/w/index.php"


def _info():
    return WikiInfo(api=API, articlepath=ARTICLE, script=SCRIPT, realurl="https://example.org", is_allowed=True)


def _wiki():
    wiki = WikiLib(API)
    wiki.wiki_info = _info()
    wiki.get_page_body_class = AsyncMock(return_value=[])
    return wiki


def _page_response(**extra):
    return {
        "query": {"pages": {"1": {"pageid": 1, "title": "Target", "fullurl": ARTICLE.replace("$1", "Target"), **extra}}}
    }


def _session(mode="off", buttons=False):
    return MessageSession(
        session_info=SessionInfo(
            target_id="TEST|Group|wiki-query-fixes",
            target_from="TEST|Group",
            client_name="TEST",
            sender_id="TEST|1",
            locale=Locale("zh_cn"),
            support_image=True,
            support_button=buttons,
            target_union_info=SimpleNamespace(target_data={"wiki_render_mode": mode}),
        )
    )


async def _test_redirect_fragments():
    for explicit in (False, True):
        wiki = _wiki()
        response = _page_response(extract="Wrong lead summary")
        response["query"].update(
            {
                "normalized": [{"from": "alias", "to": "Alias"}],
                "converted": [{"from": "Alias", "to": "Converted"}],
                "redirects": [
                    {"from": "Converted", "to": "Intermediate"},
                    {"from": "Intermediate", "to": "Target", "tofragment": "Target section"},
                ],
            }
        )
        wiki.wiki_info.extensions = ["TextExtracts"]
        wiki.get_json = AsyncMock(
            side_effect=[
                response,
                {
                    "parse": {
                        "sections": [
                            {"anchor": "Target_section"},
                            {"anchor": "Explicit"},
                        ]
                    }
                },
            ]
        )
        result = await wiki.parse_page_info("alias#Explicit" if explicit else "alias")
        expected = "Explicit" if explicit else "Target_section"
        assert result.title == "Target" and result.before_title == "alias"
        assert result.selected_section == expected and not result.invalid_section
        assert urlsplit(result.link).fragment == expected and not result.desc
        assert "curid" not in result.link
    wiki = _wiki()
    response = _page_response()
    response["query"]["redirects"] = [{"from": "Alias", "to": "Target", "tofragment": "25%25"}]
    wiki.get_json = AsyncMock(side_effect=[response, {"parse": {"sections": [{"anchor": "25%25"}]}}])
    result = await wiki.parse_page_info("Alias")
    assert result.selected_section == "25%25" and not result.invalid_section
    assert urlsplit(result.link).fragment == "25%2525"
    return True


async def _test_targeted_template_and_language_query():
    wiki = _wiki()
    wiki.get_json = AsyncMock(return_value=_page_response())
    await wiki.parse_page_info("Target", lang="en")
    params = wiki.get_json.await_args_list[0].kwargs
    assert params["lllang"] == "en" and params["tllimit"] == "max"
    assert set(params["tltemplates"].split("|")) == {
        "Template:Documentation",
        "Template:Disambiguation",
        "Template:Version disambiguation",
    }
    return True


async def _test_language_url_without_interwiki_mapping():
    source = _wiki()
    target_info = WikiInfo(
        api="https://target.org/api.php",
        articlepath="https://target.org/index.php?title=$1",
        script="https://target.org/index.php",
        is_allowed=True,
    )
    calls = []

    async def get_json(wiki, **kwargs):
        calls.append((wiki.wiki_info.api, kwargs))
        if wiki.wiki_info.api == API:
            return _page_response(
                langlinks=[{"lang": "en", "url": "https://target.org/index.php?title=Different+title"}]
            )
        return _page_response()

    with (
        patch.object(WikiLib, "get_json", new=get_json),
        patch.object(WikiLib, "get_page_body_class", new=AsyncMock(return_value=[])),
        patch.object(WikiLib, "check_wiki_available", new=AsyncMock(return_value=WikiStatus(True, target_info, ""))),
    ):
        result = await source.parse_page_info("Target", lang="en")
    assert result.info.api == target_info.api
    assert calls[1][1]["titles"] == "Different title"
    return True


def _revision_response():
    return _page_response(
        revisions=[{"revid": 42, "slots": {"main": {"*": "Historical lead.\n== Old section ==\nHistorical section."}}}]
    )


async def _test_revision_content_and_sections():
    wiki = _wiki()
    wiki.wiki_info.extensions = ["TextExtracts"]
    wiki.get_json = AsyncMock(return_value=_revision_response())
    result = await wiki.parse_page_info("Target?oldid=42")
    assert result.desc == "Historical lead." and result.revision_id == 42
    assert result.link == SCRIPT + "?oldid=42"
    assert wiki.get_json.await_args.kwargs["revids"] == 42
    assert "extracts" not in wiki.get_json.await_args.kwargs["prop"]
    assert not wiki.get_page_body_class.await_count and result.file is None
    wiki.get_json = AsyncMock(
        side_effect=[
            _revision_response(),
            {
                "parse": {
                    "sections": [{"anchor": "Old_section"}],
                    "text": "<h2 id='Old_section'>Old section</h2>",
                }
            },
        ]
    )
    result = await wiki.parse_page_info("Target?oldid=42#Old_section", check_render=True)
    assert result.selected_section == "Old_section" and result.renderable and not result.invalid_section
    assert result.desc == "Historical section."
    assert wiki.get_json.await_args.kwargs["oldid"] == 42
    callback = _build_section_callback(result)
    with patch("modules.wiki.wiki.query_pages", new=AsyncMock()) as query:
        await callback(SimpleNamespace(as_display=lambda **_: "1"))
    assert query.await_args.kwargs["title"] == "Target?oldid=42#Old_section"
    return True


async def _test_invalid_revision_and_hidden_content():
    wiki = _wiki()
    wiki.get_json = AsyncMock()
    for title in ("Target?oldid=bad", "Target?oldid=-1", "Target?oldid=42&oldid=43"):
        try:
            await wiki.parse_page_info(title)
        except InvalidWikiError:
            pass
        else:
            return False
    assert not wiki.get_json.await_count
    wiki.get_json = AsyncMock(return_value=_page_response(revisions=[{"revid": 42, "texthidden": ""}]))
    result = await wiki.parse_page_info("Target?oldid=42")
    assert result.link.endswith("oldid=42") and not result.desc
    wiki.get_json = AsyncMock(return_value={"query": {"badrevids": {"42": {"revid": 42, "missing": ""}}}})
    try:
        await wiki.parse_page_info("Target?oldid=42")
    except InvalidWikiError:
        return True
    return False


async def _test_interwiki_revision_uses_target_site():
    source = _wiki()
    target_info = WikiInfo(
        api="https://target.org/api.php",
        articlepath="https://target.org/wiki/$1",
        script="https://target.org/index.php",
        is_allowed=True,
    )
    calls = []

    async def get_json(wiki, **kwargs):
        calls.append((wiki.wiki_info.api, kwargs))
        if wiki.wiki_info.api == API:
            assert "revids" not in kwargs and kwargs["titles"] == "en:Requested"
            return {
                "query": {
                    "interwiki": [
                        {
                            "title": "en:Requested",
                            "iw": "en",
                            "url": "https://target.org/wiki/Target",
                        }
                    ]
                }
            }
        return _revision_response()

    with (
        patch.object(WikiLib, "get_json", new=get_json),
        patch.object(WikiLib, "check_wiki_available", new=AsyncMock(return_value=WikiStatus(True, target_info, ""))),
    ):
        result = await source.parse_page_info("en:Requested?oldid=42", inline=True)
    assert result.info.api == target_info.api and result.revision_id == 42
    assert result.link == target_info.script + "?oldid=42"
    assert calls[-1][1]["revids"] == 42
    return True


async def _test_api_errors_warnings_and_invalid_response():
    wiki = _wiki()
    for response in ({"error": {"code": "maxlag"}}, {"error": {"code": "permissiondenied"}}):
        with patch("modules.wiki.utils.wikilib.get_url", new=AsyncMock(return_value=response)):
            try:
                await wiki.get_json(action="query", titles="Target")
            except WikiAPIError as error:
                assert error.code == response["error"]["code"] and error.code in str(error)
            else:
                return False
    response = {"warnings": {"query": {"*": "Deprecated parameter"}}, "query": {"pages": {}}}
    with patch("modules.wiki.utils.wikilib.get_url", new=AsyncMock(return_value=response)):
        assert await wiki.get_json(action="query", titles="Target") == response
    with patch("modules.wiki.utils.wikilib.get_url", new=AsyncMock(return_value=[])):
        try:
            await wiki.get_json(action="query", titles="Target")
        except InvalidWikiError:
            return True
    return False


async def _test_parse_requests_are_reused():
    wiki = WikiLib(API)
    wiki.wiki_info = _info()
    wiki.get_json = AsyncMock(
        return_value={
            "parse": {
                "headhtml": "<html><head></head><body class='ns-0'></body></html>",
                "text": "<table class='infobox'><tr><td>Example</td></tr></table>",
            }
        }
    )
    assert await wiki.get_page_body_class("Target", include_text=True) == ["ns-0"]
    assert await wiki.check_page_renderable("Target")
    assert wiki.get_json.await_count == 1
    return True


async def _test_media_dispatch():
    info = SimpleNamespace(support_image=True, support_audio=True, support_video=True)
    with (
        patch("modules.wiki.utils.media.download", new=AsyncMock(return_value="/tmp/wiki-test.mp4")),
        patch("modules.wiki.utils.media.filetype.guess", return_value=SimpleNamespace(extension="mp4")),
    ):
        preview = await file_preview("https://example.org/video.mp4", info)
    assert len(preview) == 1 and isinstance(list(preview)[0], VideoElement)
    with (
        patch("modules.wiki.utils.media.download", new=AsyncMock(return_value="/tmp/wiki-test.svg")),
        patch("modules.wiki.utils.media.filetype.guess", return_value=None),
        patch("modules.wiki.utils.media.check_svg", return_value=True),
        patch("modules.wiki.utils.media.svg_render", new=AsyncMock(return_value=[Image("/tmp/render.png")])),
    ):
        preview = await file_preview("https://example.org/image.svg", info)
    assert len(preview) == 1 and isinstance(list(preview)[0], ImageElement)
    with (
        patch("modules.wiki.utils.media.download", new=AsyncMock(return_value="/tmp/wiki-test.unknown")),
        patch("modules.wiki.utils.media.filetype.guess", return_value=None),
        patch("modules.wiki.utils.media.check_svg", return_value=False),
    ):
        assert not await file_preview("https://example.org/unknown", info)
    with patch("modules.wiki.utils.media.download", new=AsyncMock(side_effect=RuntimeError("Download failed"))):
        assert not await file_preview("https://example.org/unavailable", info)
    info.support_video = info.support_image = info.support_audio = False
    with patch("modules.wiki.utils.media.download", new=AsyncMock()) as download:
        assert not await file_preview("https://example.org/unknown", info) and not download.await_count
    return True


async def _test_url_target_keeps_revision_and_fragment():
    wiki = _wiki()
    wiki.parse_page_info = AsyncMock(return_value=PageInfo(info=_info(), title="Target"))
    session = _session()
    await _read_url_page(wiki, "https://example.org/wiki/Target?oldid=42#Old_section", session, check_render=True)
    assert wiki.parse_page_info.await_args.args == ("https://example.org/wiki/Target?oldid=42#Old_section",)
    await _read_url_page(wiki, SCRIPT + "?title=Target&variant=zh-cn#Section", session, check_render=False)
    assert wiki.parse_page_info.await_args.args == ("Target?variant=zh-cn#Section",)
    await _read_url_page(wiki, ARTICLE.replace("$1", "Target") + "?oldid=0", session, check_render=False)
    assert wiki.parse_page_info.await_args.args == ("Target",)
    return True


async def _test_url_render_modes():
    for mode in ("off", "button", "auto"):
        session = _session(mode, buttons=True)
        session.matched_msg = [ARTICLE.replace("$1", "Target") + "#Section"]
        page = PageInfo(
            info=_info(),
            title="Target",
            link=session.matched_msg[0],
            selected_section="Section",
            renderable=True,
            desc="Redundant section summary",
        )
        sent = []

        async def background(_session, factory, **_kwargs):
            await factory()

        async def send(self, chain=None, **kwargs):
            sent.append((MessageChain.assign(chain), kwargs))
            return SimpleNamespace(message_id=[str(len(sent))])

        with (
            patch.object(
                WikiLib,
                "check_wiki_info_from_database_cache",
                new=AsyncMock(return_value=WikiStatus(True, _info(), "")),
            ),
            patch.object(WikiLib, "check_wiki_available", new=AsyncMock(return_value=WikiStatus(True, _info(), ""))),
            patch("modules.wiki.inline._read_url_page", new=AsyncMock(return_value=page)),
            patch("modules.wiki.inline._start_background_with_release", new=background),
            patch(
                "modules.wiki.inline.generate_screenshot", new=AsyncMock(return_value=["/tmp/preview.png"])
            ) as auto_render,
            patch(
                "modules.wiki.wiki.generate_screenshot", new=AsyncMock(return_value=["/tmp/preview.png"])
            ) as button_render,
            patch.object(Bot.Info, "web_render_status", True),
            patch.object(MessageSession, "send_message", new=send),
        ):
            await _parse_wiki_urls(session)
            if mode == "off":
                assert not sent and not auto_render.await_count and not button_render.await_count
            elif mode == "button":
                assert len(sent) == 1 and not auto_render.await_count and not button_render.await_count
                assert any(isinstance(item, ButtonFrameElement) for item in sent[0][0])
                assert not any(isinstance(item, PlainElement) and "Redundant" in item.text for item in sent[0][0])
                with patch.object(MessageSession, "as_display", return_value="wiki_render_preview"):
                    await sent[0][1]["callback"](session)
                assert button_render.await_count == 1
            else:
                assert len(sent) == 1 and auto_render.await_count == 1
                assert auto_render.await_args.kwargs["section"] == "Section"
    return True


async def _test_search_limit_callback_and_more_link():
    for buttons in (False, True):
        session = _session(buttons=buttons)
        captured = {}

        async def search(wiki, title, **_):
            wiki.wiki_info = _info()
            return [f"Result {number}" for number in range(1, 11)]

        async def send(self, chain=None, **kwargs):
            captured["chain"] = MessageChain.assign(chain)
            captured["callback"] = kwargs["callback"]

        target = SimpleNamespace(api_link=API, interwikis={}, headers={}, prefix="Prefix:")
        with (
            patch("modules.wiki.search.WikiTargetInfo.get_by_target_id", new=AsyncMock(return_value=target)),
            patch("modules.wiki.search.finish_if_wiki_blocked", new=AsyncMock()),
            patch.object(WikiLib, "search_page", new=search),
            patch.object(MessageSession, "send_message", new=send),
        ):
            await search_pages(session, "Needle")
        more = next(
            item
            for item in captured["chain"]
            if isinstance(item, I18NContextElement) and item.key == "wiki.message.search.more"
        )
        link = list(more.kwargs["url"])[0].url
        assert parse_qs(urlsplit(link).query)["search"] == ["Prefix:Needle"]
        for item in captured["chain"]:
            if isinstance(item, ButtonFrameElement):
                assert sum(len(row.buttons) for row in item.rows) == 5
            if isinstance(item, PlainElement):
                assert "Result 6" not in item.text
        with (
            patch("modules.wiki.search.query_pages", new=AsyncMock()) as query,
            patch.object(MessageSession, "finish", new=AsyncMock()),
        ):
            for value in ("0", "-1", "6"):
                with patch.object(MessageSession, "as_display", return_value=value):
                    await captured["callback"](session)
            assert not query.await_count
            with patch.object(MessageSession, "as_display", return_value="1"):
                await captured["callback"](session)
            assert query.await_args.args == (session, "Result 1")
            assert query.await_args.kwargs == {"start_wiki_api": API, "use_prefix": False}
    return True


async def _test_partial_query_failure_keeps_success():
    session = _session()
    sent = []
    target = SimpleNamespace(api_link=API, interwikis={}, headers={}, prefix=None)

    async def parse(wiki, title=None, **_):
        if title == "Bad":
            raise WikiAPIError("maxlag")
        return PageInfo(info=_info(), title="Good", link=ARTICLE.replace("$1", "Good"), desc="Good summary")

    async def finish(self, chain=None, **_):
        sent.append(MessageChain.assign(chain))
        raise SessionFinished

    with (
        patch("modules.wiki.wiki.WikiTargetInfo.get_by_target_id", new=AsyncMock(return_value=target)),
        patch("modules.wiki.wiki.finish_if_wiki_blocked", new=AsyncMock()),
        patch.object(WikiLib, "parse_page_info", new=parse),
        patch.object(MessageSession, "hold", new=AsyncMock()),
        patch.object(MessageSession, "release", new=AsyncMock()),
        patch.object(MessageSession, "finish", new=finish),
    ):
        try:
            await query_pages(session, ["Bad", "Good"])
        except SessionFinished:
            pass
    assert len(sent) == 1
    text = sent[0].to_str()
    assert "Good summary" in text and "maxlag" in text
    return True


async def _test_search_error_is_not_empty_result():
    session = _session()
    target = SimpleNamespace(api_link=API, interwikis={}, headers={}, prefix=None)
    with (
        patch("modules.wiki.search.WikiTargetInfo.get_by_target_id", new=AsyncMock(return_value=target)),
        patch("modules.wiki.search.finish_if_wiki_blocked", new=AsyncMock()),
        patch.object(WikiLib, "search_page", new=AsyncMock(side_effect=WikiAPIError("maxlag"))),
        patch.object(MessageSession, "finish", new=AsyncMock(side_effect=SessionFinished)) as finish,
    ):
        try:
            await search_pages(session, "Needle")
        except SessionFinished:
            pass
    assert "maxlag" in str(finish.await_args.args[0])
    return True


async def _test_interwiki_search_link_and_mode():
    source = _wiki()
    source.wiki_info.interwiki = {"en": "https://target.org/wiki/$1"}
    target_info = WikiInfo(
        api="https://target.org/api.php",
        articlepath="https://target.org/wiki/$1",
        script="https://target.org/index.php",
        is_allowed=False,
    )
    response = {"query": {"search": [{"title": "Result"}]}}
    with (
        patch.object(WikiLib, "get_json", new=AsyncMock(return_value=response)) as request,
        patch.object(WikiLib, "check_wiki_available", new=AsyncMock(return_value=WikiStatus(True, target_info, ""))),
    ):
        assert await source.search_page("en:Needle", srwhat="title") == ["en:Result"]
    assert request.await_args.kwargs["srwhat"] == "title"
    assert source.search_link.url.startswith(target_info.script)
    assert parse_qs(urlsplit(source.search_link.url).query)["search"] == ["Needle"]
    return True


async def _test_query_cancellation_propagates():
    session = _session()
    target = SimpleNamespace(api_link=API, interwikis={}, headers={}, prefix=None)
    with (
        patch("modules.wiki.wiki.WikiTargetInfo.get_by_target_id", new=AsyncMock(return_value=target)),
        patch("modules.wiki.wiki.finish_if_wiki_blocked", new=AsyncMock()),
        patch.object(WikiLib, "parse_page_info", new=AsyncMock(side_effect=asyncio.CancelledError)),
        patch.object(MessageSession, "hold", new=AsyncMock()),
        patch.object(MessageSession, "release", new=AsyncMock()) as release,
        patch.object(MessageSession, "send_message", new=AsyncMock()) as send,
    ):
        try:
            await query_pages(session, "Target")
        except asyncio.CancelledError:
            assert release.await_count == 1 and not send.await_count
            return True
    return False


@func_case
async def test_wiki_query_fixes(tester: Tester):
    for function, note in [
        (_test_redirect_fragments, "归一化与连续重定向保留章节，显式章节优先"),
        (_test_targeted_template_and_language_query, "语言与模板使用定向查询"),
        (_test_language_url_without_interwiki_mapping, "语言链接不要求同名 Interwiki"),
        (_test_revision_content_and_sections, "历史摘要、目录、链接与回调固定修订号"),
        (_test_invalid_revision_and_hidden_content, "无效与隐藏历史版本不混用当前内容"),
        (_test_interwiki_revision_uses_target_site, "Interwiki 修订号在目标站点查询"),
        (_test_api_errors_warnings_and_invalid_response, "API 错误区分、警告保留结果与格式校验"),
        (_test_parse_requests_are_reused, "预检查复用页面解析结果"),
        (_test_media_dispatch, "视频、SVG、未知类型和无媒体能力分派"),
        (_test_url_target_keeps_revision_and_fragment, "URL 目标保留修订号、参数及章节"),
        (_test_url_render_modes, "URL 遵守 off、button、auto 且章节无重复摘要"),
        (_test_search_limit_callback_and_more_link, "短搜索列表、网页入口与严格序号校验"),
        (_test_partial_query_failure_keeps_success, "多页查询失败不丢失成功结果"),
        (_test_search_error_is_not_empty_result, "搜索错误不会显示为未找到结果"),
        (_test_interwiki_search_link_and_mode, "跨站搜索保留搜索类型并提供目标站网页入口"),
        (_test_query_cancellation_propagates, "查询取消正确传播并释放会话"),
    ]:
        await tester.test(function, note)
    return tester
