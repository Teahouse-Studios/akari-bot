import asyncio
import base64
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from bs4 import BeautifulSoup
from PIL import Image as PILImage

from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import ButtonFrameElement, ImageElement
from core.builtins.session.info import SessionInfo
from core.builtins.session.internal import MessageSession
from core.constants.exceptions import SessionFinished
from core.i18n import Locale
from core.tester import Tester, func_case
from modules.wiki.utils import template_preview as preview
from modules.wiki.utils.preview_render import PreviewRequests
from modules.wiki.utils.preview_render import _document_resources, _remote_render, render_shell_document
from modules.wiki.utils.template_preview import TemplateInvocation, TemplatePreviewError
from modules.wiki.utils.wikilib import PageInfo, WikiInfo, WikiLib
from modules.wiki.wiki import _WikiMessageTracker, _build_template_preview_callback, query_expressions, query_pages
from modules.wiki.utils.magic import MagicRegistry

API = "https://example.org/w/api.php"
SOURCE = "{{Infobox|first|name={{Nested|x=1}}|name=second|empty=}}"


def _policy(allowed):
    return SimpleNamespace(allowed=allowed, blocked=False)


def _info(api=API):
    return WikiInfo(
        api=api,
        realurl="https://example.org",
        name="示例 Wiki",
        articlepath="https://example.org/wiki/$1",
        namespaces={"Template": 10, "模板": 10},
        default_skin="vector",
        is_allowed=True,
    )


def _session(sender="TEST|1", render="button"):
    return MessageSession(
        SessionInfo(
            target_id="TEST|Group|template-preview",
            target_from="TEST|Group",
            client_name="TEST",
            sender_id=sender,
            support_button=True,
            support_image=True,
            locale=Locale("zh_cn"),
            target_union_info=SimpleNamespace(target_data={"wiki_render_mode": render}),
        )
    )


def _invocation(source=SOURCE):
    return TemplateInvocation(source, API, "Template:Infobox", 42, _info(), {})


async def _query(*, allowed=True, title="Template:Infobox", mode="button", prefix=None, api=API, multiple=False):
    session = _session(render=mode)
    page = PageInfo(info=_info(api), title=title, id=42, link="https://example.org/wiki/" + title, status=True)
    sent = []
    target = SimpleNamespace(api_link=API, headers={}, prefix=prefix, interwikis={"other": api})

    async def finish(self, chain=None, **kwargs):
        sent.append((MessageChain.assign(chain), kwargs))
        raise SessionFinished

    async def send(self, chain=None, **kwargs):
        sent.append((MessageChain.assign(chain), kwargs))
        return SimpleNamespace(message_id=["query"])

    with (
        patch.object(Bot.Info, "web_render_status", True),
        patch.object(WikiLib, "parse_page_info", new=AsyncMock(return_value=page)) as parse,
        patch("modules.wiki.wiki.WikiTargetInfo.get_by_target_id", new=AsyncMock(return_value=target)),
        patch("modules.wiki.wiki.finish_if_wiki_blocked", new=AsyncMock()),
        patch("modules.wiki.wiki.evaluate_url_policy", return_value=_policy(allowed)),
        patch("modules.wiki.wiki._start_background_with_release", new=AsyncMock()) as preload,
        patch.object(MessageSession, "hold", new=AsyncMock()),
        patch.object(MessageSession, "release", new=AsyncMock()),
        patch.object(MessageSession, "finish", new=finish),
        patch.object(MessageSession, "send_message", new=send),
    ):
        try:
            await query_pages(
                session,
                ["Infobox", "Other"] if multiple else ["Infobox"],
                template=True,
                template_invocations={"Infobox": SOURCE},
            )
        except SessionFinished:
            pass
    buttons = [
        button
        for chain, _ in sent
        for frame in chain
        if isinstance(frame, ButtonFrameElement)
        for row in frame.rows
        for button in row.buttons
    ]
    return sent, buttons, preload, parse


def _test_parameters():
    assert preview.template_parameters(SOURCE) == ["first", "name", "{{Nested|x=1}}", "name", "second", "empty"]
    for source in ["{{Infobox}}", "{{:Article|x}}", "{{Infobox|" + "x" * 4096 + "}}", "{{Infobox|x}} trailing"]:
        try:
            preview.template_parameters(source)
        except TemplatePreviewError:
            pass
        else:
            raise AssertionError(source)
    return True


async def _test_buttons_are_whitelisted_and_preloaded():
    for mode in ["button", "auto"]:
        sent, buttons, preload, _ = await _query(mode=mode)
        assert [button.value for button in buttons] == ["wiki_template_preview", "wiki_render_delete"]
        assert buttons[0].show == "预览效果"
        assert buttons[0].permission.value == "owner" and buttons[0].click_limit == 1
        assert sent[0][1]["callback_timeout"] == 300 and preload.await_count == 1
        assert preload.await_args.kwargs["name"] == "wiki-template-preview-preload"
    for options in [dict(allowed=False), dict(title="Infobox"), dict(mode="off")]:
        _, buttons, _, _ = await _query(**options)
        assert all(button.value != "wiki_template_preview" for button in buttons)
    _, buttons, _, parse = await _query(prefix="other:", api="https://other.org/api.php")
    assert buttons[0].value == "wiki_template_preview"
    assert parse.await_args.args == () and parse.await_args.kwargs["title"] == "Template:Infobox"
    _, _, background, _ = await _query(mode="auto", multiple=True)
    assert background.await_count == 1
    return True


async def _test_expression_routing_keeps_complete_parameters():
    session = _session()
    target = SimpleNamespace(api_link=API, headers={})

    async def registry(wiki):
        wiki.wiki_info = _info()
        return MagicRegistry({"variables": [], "functionhooks": [], "magicwords": []})

    with (
        patch("modules.wiki.wiki.WikiTargetInfo.get_by_target_id", new=AsyncMock(return_value=target)),
        patch("modules.wiki.wiki.finish_if_wiki_blocked", new=AsyncMock()),
        patch("modules.wiki.wiki.get_registry", new=registry),
        patch("modules.wiki.wiki.query_pages", new=AsyncMock()) as query,
    ):
        await query_expressions(session, SOURCE + " {{Infobox|another}}", inline=True)
    assert query.await_args.kwargs["template_invocations"] == {"Infobox": SOURCE}
    assert query.await_args.kwargs["template_preview_source"] == SOURCE + " {{Infobox|another}}"
    return True


async def _test_only_parameters_are_audited():
    session = _session()
    with (
        patch.object(preview.dirty_check, "access_key_id", "configured"),
        patch.object(preview.dirty_check, "access_key_secret", "configured"),
        patch.object(preview.dirty_check, "check", new=AsyncMock(return_value=[{"status": True}] * 6)) as audit,
    ):
        await preview.check_template_parameters(SOURCE, session)
        assert audit.await_args.args == (["first", "name", "{{Nested|x=1}}", "name", "second", "empty"],)
        assert audit.await_args.kwargs == {"session": session, "force": True}
    for response, reason in [([{"status": False}] * 6, "filtered"), ([], "audit_unavailable")]:
        with (
            patch.object(preview.dirty_check, "access_key_id", "configured"),
            patch.object(preview.dirty_check, "access_key_secret", "configured"),
            patch.object(preview.dirty_check, "check", new=AsyncMock(return_value=response)),
        ):
            try:
                await preview.check_template_parameters(SOURCE, session)
            except TemplatePreviewError as error:
                assert error.key.endswith(reason)
            else:
                return False
    with patch.object(preview.dirty_check, "access_key_id", ""):
        try:
            await preview.check_template_parameters(SOURCE, session)
        except TemplatePreviewError as error:
            assert error.key.endswith("audit_unavailable")
        else:
            return False
    return True


def _test_document_preserves_effects_and_removes_input_scripts():
    parsed = {
        "headhtml": '<html lang="zh" dir="ltr"><head><link rel="stylesheet" href="/w/load.php?modules=site.styles">'
        '<noscript><link rel="stylesheet" href="/w/load.php?modules=noscript"></noscript>'
        '<script src="/w/load.php?modules=startup"></script></head><body class="skin-vector">',
        "text": '<div class="mw-parser-output"><style>.infobox{background:red}</style>'
        '<table class="infobox"><tr><td><img src="/images/icon.png" loading="lazy" onerror="bad()">'
        "</td></tr></table><script>userInput()</script></div>",
        "modules": ["ext.example"],
        "jsconfigvars": {"wgExample": "</script><script>payload()</script>"},
    }
    document, warning = preview.preview_document(parsed, _invocation(), Locale("zh_cn"))
    soup = BeautifulSoup(document, "html.parser")
    assert soup.select_one(".infobox img")["src"] == "/images/icon.png"
    assert soup.select_one(".infobox img").get("onerror") is None
    assert soup.select_one(".mw-parser-output style").get_text() == ".infobox{background:red}"
    assert soup.select_one('head script[src*="startup"]')
    assert soup.select_one('head > link[href*="modules=noscript"]')
    assert soup.html["lang"] == "zh" and soup.html["dir"] == "ltr"
    assert soup.body["class"] == ["skin-vector"]
    assert soup.base["href"] == "https://example.org/"
    assert not soup.select_one("#akari-preview-declaration")
    assert "userInput()" not in document and "\\u003c/script\\u003e" in document and not warning
    return True


def _test_watermark_is_safe_inline_css():
    title = 'Template:{{7*7}}<&"</style><script>injected()</script>'
    invocation = TemplateInvocation(SOURCE, API, title, 42, _info(), {})
    parsed = {"headhtml": "", "text": "<p>正文</p>"}
    for partial in [False, True]:
        document, warning = preview.preview_document(
            {**parsed, "parsewarnings": ["warning"] if partial else []}, invocation, Locale("zh_cn")
        )
        soup = BeautifulSoup(document, "html.parser")
        assert warning is partial
        overlay = soup.select_one("body > #akari-preview-watermark")
        assert overlay["data-preview-partial"] == str(partial).lower()
        assert overlay["aria-hidden"] == "true" and overlay.select_one("svg.akari-watermark-pattern")
        assert len(overlay.select(".akari-watermark-row")) == 4
        assert overlay.select_one("pattern")["height"] == "384"
        css = soup.style.get_text()
        for index, variant in enumerate(("normal", "partial")):
            text = overlay.select_one(".akari-watermark-" + variant)
            assert not text.find("script")
            assert text.text == Locale("zh_cn").t(
                "wiki.message.template_preview.watermark",
                title=title,
                status=" · 部分资源未加载" if index else "",
            )
        assert all("injected()" not in script.get_text() for script in soup.find_all("script"))
        assert overlay.select_one("pattern")["patternunits"] == "userSpaceOnUse"
        assert "getComputedTextLength()" in document
        assert "rotate(-30deg)" in css
    return True


def _test_single_template_document_adds_css_panel():
    parsed = {
        "headhtml": "<html><head></head><body>",
        "text": '<div class="mw-parser-output"><table class="infobox"><tr><td>内容</td></tr></table></div>',
    }
    document, warning = preview.preview_document(parsed, _invocation(), Locale("zh_cn"), single_template=True)
    soup = BeautifulSoup(document, "html.parser")
    assert not warning
    assert soup.select_one("#akari-template-output .infobox")
    assert soup.select_one("#akari-preview-css-panel .akari-css-title").text == "样式属性"
    assert "grid-template-columns" in soup.find("style").get_text()
    assert "akariFillCssPanel" in document
    return True


async def _test_whole_message_preview_keeps_multiple_templates():
    first = _invocation("{{Infobox|title=一}}")
    second = TemplateInvocation("{{Color|red|二}}", API, "Template:Color", 43, _info(), {})
    requests = SimpleNamespace(
        api_json=AsyncMock(
            side_effect=[
                {
                    "query": {
                        "pages": [
                            {"ns": 10, "title": "Template:Infobox", "pageid": 42},
                            {"ns": 10, "title": "Template:Color", "pageid": 43},
                        ]
                    }
                },
                {"parse": {"text": "<div>一<span>二</span></div>", "headhtml": ""}},
            ]
        )
    )
    manager = AsyncMock()
    manager.__aenter__.return_value = requests
    source = "前缀 {{Infobox|title=一}} 中间 {{Color|red|二}} 后缀"
    with (
        patch.object(preview, "evaluate_url_policy", return_value=_policy(True)),
        patch.object(preview, "check_template_parameters", new=AsyncMock()),
        patch.object(preview, "PreviewRequests", return_value=manager),
        patch.object(preview, "_render_template_shell", new=AsyncMock(side_effect=RuntimeError("shell unavailable"))),
        patch.object(
            preview, "render_preview_document", new=AsyncMock(return_value=(PILImage.new("RGB", (12, 8)), False))
        ),
    ):
        image = await preview.generate_template_preview(first, _session(), source=source, invocations=[first, second])
    assert isinstance(image, PILImage.Image)
    args = requests.api_json.await_args_list[1].kwargs
    assert args["text"] == "前缀 {{Template:Infobox|title=一}} 中间 {{Template:Color|red|二}} 后缀"
    return True


async def _test_generation_uses_actual_template_and_only_read_api():
    invocation, session = _invocation(), _session()
    requests = SimpleNamespace(
        api_json=AsyncMock(
            side_effect=[
                {"query": {"pages": [{"ns": 10, "title": "Template:Infobox", "pageid": 42}]}},
                {"parse": {"text": '<div class="mw-parser-output">Expanded body</div>', "headhtml": ""}},
            ]
        )
    )
    manager = AsyncMock()
    manager.__aenter__.return_value = requests
    with (
        patch.object(preview, "evaluate_url_policy", return_value=_policy(True)),
        patch.object(preview, "check_template_parameters", new=AsyncMock()) as audit,
        patch.object(preview, "PreviewRequests", return_value=manager),
        patch.object(preview, "_render_template_shell", new=AsyncMock(side_effect=RuntimeError("shell unavailable"))),
        patch.object(
            preview, "render_preview_document", new=AsyncMock(return_value=(PILImage.new("RGBA", (10, 10)), False))
        ) as render,
    ):
        image = await preview.generate_template_preview(invocation, session)
    assert isinstance(image, PILImage.Image)
    assert image is render.return_value[0]
    assert audit.await_args.args == (SOURCE, session)
    parse_args = requests.api_json.await_args_list[1].kwargs
    assert parse_args["action"] == "parse" and parse_args["preview"] == 1
    assert parse_args["text"] == SOURCE.replace("{{Infobox", "{{Template:Infobox", 1)
    assert parse_args["title"] == invocation.title and parse_args["useskin"] == "vector"
    with patch.object(preview, "evaluate_url_policy", return_value=_policy(False)):
        try:
            await preview.generate_template_preview(invocation, session)
        except TemplatePreviewError as error:
            assert error.key.endswith("not_allowed")
        else:
            return False
    return True


async def _test_callback_identity_once_and_delete():
    owner = _session()
    click = SimpleNamespace(session_info=_session().session_info)
    tracker = _WikiMessageTracker(owner)
    click.as_display = lambda text_only=False: "wiki_template_preview"
    click.send_message = AsyncMock(return_value=SimpleNamespace(message_id=["preview"]))

    async def background(session, factory, **_):
        return asyncio.create_task(factory())

    with (
        patch.object(Bot.Info, "web_render_status", True),
        patch("modules.wiki.wiki.evaluate_url_policy", return_value=_policy(True)),
        patch(
            "modules.wiki.wiki.generate_template_preview", new=AsyncMock(return_value=PILImage.new("RGB", (20, 20)))
        ) as generate,
        patch("modules.wiki.wiki._start_background_with_release", new=background),
        patch.object(tracker, "delete", new=AsyncMock()) as delete,
    ):
        callback = _build_template_preview_callback(_invocation(), tracker)
        other = SimpleNamespace(session_info=_session("TEST|2").session_info)
        other.as_display = click.as_display
        await callback(other)
        assert generate.await_count == 0
        await callback(click)
        await callback(click)
        assert generate.await_count == 1
        assert isinstance(click.send_message.await_args.args[0], ImageElement)
        assert tracker.message_ids == ["preview"]
        click.as_display = lambda text_only=False: "wiki_render_delete"
        await callback(click)
        assert delete.await_count == 1
    return True


async def _test_request_whitelist_redirects_and_resources():
    calls = []

    async def handler(request):
        calls.append(str(request.url))
        if "redirect" in request.url.params:
            return httpx.Response(302, headers={"location": "https://untrusted.org/api.php"})
        return httpx.Response(200, json={"query": {"pages": []}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with (
        patch("modules.wiki.utils.preview_render.httpx.AsyncClient", return_value=client),
        patch("modules.wiki.utils.preview_render.private_ip_check", new=AsyncMock()),
        patch("modules.wiki.utils.preview_render.evaluate_url_policy", side_effect=lambda url: _policy(url == API)),
    ):
        async with PreviewRequests(API, "https://example.org", {}) as requests:
            assert await requests.api_json(action="query") == {"query": {"pages": []}}
            assert requests.resource_allowed("https://example.org/images/icon.png", "image")
            assert not requests.resource_allowed("https://example.org/w/api.php?action=edit", "image")
            assert not requests.resource_allowed("https://example.org/arbitrary.js", "script")
            assert not requests.resource_allowed("https://untrusted.org/icon.png", "image")
            try:
                await requests.api_json(action="query", redirect=1)
            except ValueError:
                pass
            else:
                return False
    assert len(calls) == 2 and all(url.startswith(API) for url in calls)
    return True


async def _test_remote_inlines_styles_and_images():
    buffer = BytesIO()
    PILImage.new("RGB", (20, 20), "red").save(buffer, "PNG")
    png = buffer.getvalue()
    requests = PreviewRequests(API, "https://example.org", {})

    async def fetch(url, kind, **_):
        if kind == "stylesheet":
            return b'.infobox{background:url("/images/background.png");border:1px solid red}', "text/css", url
        return png, "image/png", url

    requests.fetch = fetch
    parsed = {
        "headhtml": '<html><head><link rel="stylesheet" href="/w/load.php?only=styles"></head><body>',
        "text": '<div class="mw-parser-output"><table class="infobox"><tr><td>'
        '<img src="/images/item.png"></td></tr></table></div>',
    }
    document, _ = preview.preview_document(parsed, _invocation(), Locale("zh_cn"))
    with patch(
        "modules.wiki.utils.preview_render.web_render.element_screenshot",
        new=AsyncMock(return_value=[base64.b64encode(png).decode()]),
    ) as render:
        image = await _remote_render(_document_resources(document, requests), requests, Locale("zh_cn"))
    options = render.await_args.args[0]
    soup = BeautifulSoup(options.content, "html.parser")
    assert image.size == (20, 20) and options.element == "body > #mw-content-text"
    assert soup.select_one("body > #akari-preview-watermark")["data-preview-partial"] == "true"
    assert all(script.get("data-akari-preview-script") == "watermark" for script in soup.find_all("script"))
    assert soup.img["src"].startswith("data:image/png;base64,")
    styles = "\n".join(str(style.string or "") for style in soup.find_all("style"))
    assert soup.select_one("#akari-preview-watermark pattern")
    assert ".infobox" in styles and "data:image/png;base64," in styles
    assert soup.select_one('meta[http-equiv="Content-Security-Policy"]') and not soup.select_one("link[href]")
    return True


async def _test_long_input_posts_only_read_requests():
    seen = []

    async def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"parse": {"text": "ok"}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with (
        patch("modules.wiki.utils.preview_render.httpx.AsyncClient", return_value=client),
        patch("modules.wiki.utils.preview_render.private_ip_check", new=AsyncMock()),
        patch("modules.wiki.utils.preview_render.evaluate_url_policy", side_effect=lambda url: _policy(url == API)),
    ):
        async with PreviewRequests(API, "https://example.org", {}) as requests:
            await requests.api_json(action="parse", text="参数" * 1000)
            assert seen[0].method == "POST" and str(seen[0].url) == API
            assert seen[0].headers["Promise-Non-Write-API-Action"] == "true"
            try:
                await requests.api_json(action="edit", text="修改")
            except ValueError:
                pass
            else:
                return False
    assert len(seen) == 1
    return True


async def _test_deletion_cancels_pending_render():
    owner = _session()
    click = SimpleNamespace(
        session_info=owner.session_info,
        as_display=lambda text_only=False: "wiki_template_preview",
        send_message=AsyncMock(),
    )
    tracker = _WikiMessageTracker(owner)
    started = asyncio.Event()
    stopped = asyncio.Event()

    async def render(*_):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    async def background(session, factory, **_):
        return asyncio.create_task(factory())

    with (
        patch.object(Bot.Info, "web_render_status", True),
        patch("modules.wiki.wiki.evaluate_url_policy", return_value=_policy(True)),
        patch("modules.wiki.wiki.generate_template_preview", new=render),
        patch("modules.wiki.wiki._start_background_with_release", new=background),
    ):
        callback = _build_template_preview_callback(_invocation(), tracker)
        first = asyncio.create_task(callback(click))
        await started.wait()
        click.as_display = lambda text_only=False: "wiki_render_delete"
        await callback(click)
        await asyncio.gather(first, return_exceptions=True)
    assert tracker.deleted and stopped.is_set() and click.send_message.await_count == 0
    return True


async def _test_dual_render_uses_shell_or_concurrent_fallback():
    for outcome in ("shell", "failed", "timeout", "fallback_failed"):
        api_image = PILImage.new("RGB", (12, 8), "red")
        shell_image = PILImage.new("RGB", (12, 8), "blue")
        requests = SimpleNamespace(
            api_json=AsyncMock(
                side_effect=[
                    {"query": {"pages": [{"ns": 10, "title": "Template:Infobox", "pageid": 42}]}},
                    {"parse": {"text": '<div class="mw-parser-output"><p>结果</p></div>', "headhtml": ""}},
                ]
            )
        )
        manager = AsyncMock()
        manager.__aenter__.return_value = requests
        api_started, shell_started = asyncio.Event(), asyncio.Event()
        api_cancelled, shell_cancelled = asyncio.Event(), asyncio.Event()

        async def api(*_):
            api_started.set()
            await shell_started.wait()
            if outcome == "shell":
                try:
                    await asyncio.Event().wait()
                finally:
                    api_cancelled.set()
            if outcome == "fallback_failed":
                raise RuntimeError("API renderer unavailable")
            return api_image, False

        async def shell(*_):
            shell_started.set()
            await api_started.wait()
            if outcome == "timeout":
                try:
                    await asyncio.Event().wait()
                finally:
                    shell_cancelled.set()
            if outcome == "failed":
                raise RuntimeError("WAF")
            return shell_image

        with (
            patch.object(preview, "evaluate_url_policy", return_value=_policy(True)),
            patch.object(preview, "check_template_parameters", new=AsyncMock()),
            patch.object(preview, "PreviewRequests", return_value=manager),
            patch.object(preview, "render_preview_document", new=api),
            patch.object(preview, "_render_template_shell", new=shell),
            patch.object(preview, "TEMPLATE_SHELL_TIMEOUT", 0.03),
        ):
            result = await preview.generate_template_preview(_invocation(), _session())
        assert result is (api_image if outcome in {"failed", "timeout"} else shell_image), outcome
        assert requests.api_json.await_count == 2 and api_started.is_set() and shell_started.is_set()
        assert not preview._ACTIVE_SENDERS
        if outcome == "shell":
            assert api_cancelled.is_set()
        if outcome == "timeout":
            assert shell_cancelled.is_set()
    return True


async def _test_cancel_cleans_both_template_renderers():
    requests = SimpleNamespace(
        api_json=AsyncMock(
            side_effect=[
                {"query": {"pages": [{"ns": 10, "title": "Template:Infobox", "pageid": 42}]}},
                {"parse": {"text": "正文", "headhtml": ""}},
            ]
        )
    )
    manager = AsyncMock()
    manager.__aenter__.return_value = requests
    started = [asyncio.Event(), asyncio.Event()]
    stopped = [asyncio.Event(), asyncio.Event()]

    async def render(index):
        started[index].set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped[index].set()

    with (
        patch.object(preview, "evaluate_url_policy", return_value=_policy(True)),
        patch.object(preview, "check_template_parameters", new=AsyncMock()),
        patch.object(preview, "PreviewRequests", return_value=manager),
        patch.object(preview, "render_preview_document", new=lambda *_: render(0)),
        patch.object(preview, "_render_template_shell", new=lambda *_: render(1)),
    ):
        task = asyncio.create_task(preview.generate_template_preview(_invocation(), _session()))
        await asyncio.gather(*(event.wait() for event in started))
        task.cancel()
        result = await asyncio.gather(task, return_exceptions=True)
    assert isinstance(result[0], asyncio.CancelledError)
    assert all(event.is_set() for event in stopped) and not preview._ACTIVE_SENDERS
    return True


async def _test_template_preload_is_cached_until_clicked():
    owner = _session()
    tracker = _WikiMessageTracker(owner)
    click = SimpleNamespace(session_info=owner.session_info, send_message=AsyncMock())
    click.as_display = lambda text_only=False: "wiki_template_preview"

    async def background(session, factory, **_):
        return asyncio.create_task(factory())

    with (
        patch.object(Bot.Info, "web_render_status", True),
        patch("modules.wiki.wiki.evaluate_url_policy", return_value=_policy(True)),
        patch(
            "modules.wiki.wiki.generate_template_preview", new=AsyncMock(return_value=PILImage.new("RGB", (8, 8)))
        ) as generate,
        patch("modules.wiki.wiki._start_background_with_release", new=background),
    ):
        callback = _build_template_preview_callback(_invocation(), tracker, preload_session=owner)
        await (await callback.preload())
        assert generate.await_count == 1 and click.send_message.await_count == 0
        await callback(click)
        await callback(click)
        assert generate.await_count == 1 and click.send_message.await_count == 1
    return True


def _test_shell_fragment_preserves_site_container():
    parsed = {
        "text": '<div class="mw-parser-output"><div style="display:flex">内容</div><script>injected()</script></div>',
        "headhtml": "",
    }
    document, _ = preview.preview_document(parsed, _invocation(), Locale("zh_cn"), single_template=True, shell=True)
    soup = BeautifulSoup(document, "html.parser")
    assert soup.select_one('.mw-parser-output[data-akari-template-output] > [style="display:flex"]')
    assert not soup.select_one("#akari-template-output") and not soup.select_one("#mw-content-text")
    assert soup.select_one("#akari-preview-css-panel") and soup.select_one("#akari-preview-watermark")
    assert "injected()" not in document and "akariFillCssPanel" in document
    assert preview._template_page_url(_invocation()) == "https://example.org/"
    return True


async def _test_remote_shell_keeps_ancestors_and_rejects_other_origins():
    parsed = {"text": '<div class="mw-parser-output"><div class="box">结果</div></div>', "headhtml": ""}
    fragment, _ = preview.preview_document(parsed, _invocation(), Locale("zh_cn"), single_template=True, shell=True)
    page_url = preview._template_page_url(_invocation())
    requests = PreviewRequests(API, "https://example.org", {})
    requests.fetch = AsyncMock(
        return_value=(
            b"<html><head><style>.skin-special #content article .mw-body-content > .mw-parser-output > .box {display:flex}</style></head>"
            b'<body class="skin-special"><main id="content"><article><div id="mw-content-text" class="mw-body-content">'
            b"<p>Old body</p><script>siteCode()</script></div></article></main></body></html>",
            "text/html",
            page_url,
        )
    )
    buffer = BytesIO()
    PILImage.new("RGB", (12, 8)).save(buffer, "PNG")
    with (
        patch("modules.wiki.utils.preview_render.evaluate_url_policy", return_value=_policy(True)),
        patch("modules.wiki.utils.preview_render.web_render.remote_only", True),
        patch(
            "modules.wiki.utils.preview_render.web_render.element_screenshot",
            new=AsyncMock(return_value=[base64.b64encode(buffer.getvalue()).decode()]),
        ) as screenshot,
    ):
        image, warning = await render_shell_document(fragment, parsed, page_url, requests, Locale("zh_cn"))
        assert image.size == (12, 8) and warning
        options = screenshot.await_args.args[0]
        assert options.element == "#mw-content-text"
        soup = BeautifulSoup(options.content, "html.parser")
        assert soup.select_one(".skin-special #content article .mw-body-content > .mw-parser-output > .box")
        assert soup.select_one("#akari-preview-css-panel") and soup.select_one("#akari-preview-watermark")
        assert "Old body" not in soup.text and "siteCode()" not in options.content
        assert soup.select_one('meta[http-equiv="Content-Security-Policy"]')
        calls = requests.fetch.await_count
        try:
            await render_shell_document(
                fragment, parsed, "https://untrusted.org/wiki/Template:Infobox", requests, Locale("zh_cn")
            )
        except ValueError:
            pass
        else:
            return False
        assert requests.fetch.await_count == calls
    return True


@func_case
async def test_wiki_template_preview(tester: Tester):
    for function, note in [
        (_test_parameters, "保留重复、空值及嵌套参数，拒绝无效调用"),
        (_test_buttons_are_whitelisted_and_preloaded, "白名单、命名空间、模式与站点路由控制按钮，消息发出后预载"),
        (_test_expression_routing_keeps_complete_parameters, "表达式入口将完整参数传入页面查询，同名调用绑定第一条"),
        (_test_only_parameters_are_audited, "仅审核用户参数，审核缺配置、失败与无效结果拒绝预览"),
        (_test_document_preserves_effects_and_removes_input_scripts, "保留站点样式、图片及渲染模块，参数不能注入脚本"),
        (_test_watermark_is_safe_inline_css, "CSS 水印浮层旋转 −30°，警告状态与模板标题安全转义"),
        (_test_single_template_document_adds_css_panel, "单模板预览在内容旁展示 CSS 属性面板"),
        (_test_whole_message_preview_keeps_multiple_templates, "多模板预览保留整条消息文本和全部模板"),
        (_test_generation_uses_actual_template_and_only_read_api, "核验真实模板，完整参数只读解析，撤出白名单拒绝执行"),
        (_test_callback_identity_once_and_delete, "回调仅原发送者触发一次，预览消息纳入删除追踪"),
        (_test_request_whitelist_redirects_and_resources, "API 查询参数不影响白名单，重定向与资源遵守请求范围"),
        (_test_remote_inlines_styles_and_images, "远程渲染保留表格样式与图片，资源全部内联且禁止浏览器联网"),
        (_test_long_input_posts_only_read_requests, "长参数使用只读 POST，编辑接口不能进入请求路径"),
        (_test_deletion_cancels_pending_render, "删除结果取消正在渲染的任务，禁止发送晚到图片"),
        (
            _test_dual_render_uses_shell_or_concurrent_fallback,
            "双路并发：优先真实外壳，失败或超时复用 API 兜底，取消未选中的任务",
        ),
        (_test_cancel_cleans_both_template_renderers, "取消模板预览时收尾两条渲染链并释放发送者状态"),
        (_test_template_preload_is_cached_until_clicked, "预载只缓存图片，点击才发送且不重复渲染"),
        (_test_shell_fragment_preserves_site_container, "真实外壳保留站点内容层级，共享 CSS 面板和水印，移除用户脚本"),
        (
            _test_remote_shell_keeps_ancestors_and_rejects_other_origins,
            "远端渲染保留皮肤祖先 DOM，清理原正文与脚本，拒绝站外外壳",
        ),
    ]:
        await tester.test(function, note)
    return tester
