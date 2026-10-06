import asyncio
from datetime import datetime, UTC

import orjson
import wikitextparser as wtp
from attrs import define
from bs4 import BeautifulSoup
from PIL import Image as PILImage, ImageDraw, ImageFont

from core.builtins.filter import contain_badwords
from core.builtins.message.internal import I18NContext
from core.constants.path import noto_sans_demilight_path
from core.utils import dirty_check
from core.utils.url_audit import evaluate_url_policy
from .magic import extract_expressions
from .preview_render import PreviewRequests, render_preview_document
from .wikilib import WikiInfo

MAX_TEMPLATE_LENGTH = 4096
TEMPLATE_PREVIEW_TTL = 300
TEMPLATE_PREVIEW_TIMEOUT = 30
PREVIEW_CONTEXT = "AkariBot"
_RENDER_SLOTS = asyncio.Semaphore(2)
_ACTIVE_SENDERS = set()


class TemplatePreviewError(Exception):
    def __init__(self, reason):
        self.key = "wiki.message.template_preview." + reason
        super().__init__(self.key)


@define(frozen=True)
class TemplateInvocation:
    source: str
    api: str
    title: str
    pageid: int
    wiki_info: WikiInfo
    headers: dict
    language: str | None = None


def template_parameters(source: str) -> list[str]:
    roots = extract_expressions(source)
    if len(source) > MAX_TEMPLATE_LENGTH or len(roots) != 1 or roots[0].span != (0, len(source)):
        raise TemplatePreviewError("invalid")
    root = roots[0]
    if type(root).__name__ != "Template" or not root.arguments or len(root.arguments) > 50:
        raise TemplatePreviewError("invalid")
    parsed = wtp.parse(source)
    nodes = [*parsed.templates, *parsed.parser_functions]
    if len(nodes) > 64 or any(
        sum(other.span[0] <= node.span[0] and node.span[1] <= other.span[1] for other in nodes) > 8 for node in nodes
    ):
        raise TemplatePreviewError("invalid")
    if root.name.strip().startswith(":") or "{" in root.name:
        raise TemplatePreviewError("invalid")
    return [
        part
        for argument in root.arguments
        for part in ((argument.value,) if argument.positional else (argument.name, argument.value))
        if part.strip()
    ]


async def check_template_parameters(source, session):
    parameters = template_parameters(source)
    if any(contain_badwords(parameter) for parameter in parameters):
        raise TemplatePreviewError("filtered")
    if parameters:
        if not dirty_check.access_key_id or not dirty_check.access_key_secret:
            raise TemplatePreviewError("audit_unavailable")
        try:
            checked = await dirty_check.check(parameters, session=session, force=True)
        except Exception as error:
            raise TemplatePreviewError("audit_unavailable") from error
        if len(checked) != len(parameters) or any(
            not isinstance(item, dict) or "status" not in item for item in checked
        ):
            raise TemplatePreviewError("audit_unavailable")
        if any(item["status"] is not True for item in checked):
            raise TemplatePreviewError("filtered")


def preview_document(parsed, invocation, locale):
    def value(key):
        result = parsed.get(key, "")
        return result.get("*", "") if isinstance(result, dict) else result

    body = value("text")
    head = value("headhtml")
    if not isinstance(body, str) or not body.strip() or not isinstance(head, str):
        raise TemplatePreviewError("empty")
    if len((head + body).encode()) > 1024 * 1024:
        raise TemplatePreviewError("too_large")
    soup = BeautifulSoup(head + "</body></html>", "html.parser")
    if not soup.html or not soup.head or not soup.body:
        soup = BeautifulSoup("<html><head></head><body></body></html>", "html.parser")
    soup.body.clear()
    content = soup.new_tag("div", id="mw-content-text", attrs={"class": "mw-body-content"})
    markup = BeautifulSoup(body, "html.parser")
    for tag in markup.find_all(["script", "iframe", "object", "embed", "base", "meta"]):
        tag.decompose()
    for tag in markup.find_all(True):
        for attr in list(tag.attrs):
            if attr.lower().startswith("on") or attr.lower() in {"srcdoc", "autofocus"}:
                del tag[attr]
    for image in markup.find_all("img"):
        image.attrs.pop("loading", None)
        if image.get("data-src"):
            image["src"] = image["data-src"]
        if image.get("data-srcset"):
            image["srcset"] = image["data-srcset"]
    content.append(markup)
    soup.body.append(content)
    for base in soup.find_all("base"):
        base.decompose()
    soup.head.insert(0, soup.new_tag("base", href=invocation.wiki_info.realurl.rstrip("/") + "/"))
    for tag in soup.find_all("meta"):
        if tag.get("http-equiv", "").lower() == "refresh":
            tag.decompose()
    for noscript in soup.find_all("noscript"):
        for style in noscript.find_all(["style", "link"]):
            soup.head.append(style.extract())
    style = soup.new_tag("style")
    style.string = "html,body{margin:0;background:white}#mw-content-text{display:flow-root;padding:16px}"
    soup.head.append(style)
    declaration = locale.t(I18NContext("wiki.message.template_preview.declaration").key)
    footer = soup.new_tag("div", id="akari-preview-declaration")
    footer.string = declaration
    soup.body.append(footer)
    config = parsed.get("jsconfigvars", {})
    modules = parsed.get("modules", [])
    script = soup.new_tag("script")
    script.string = (
        "window.akariPreviewReady=false;(function initialize(attempt){"
        "if(!window.mw||typeof mw.loader.using!=='function'){"
        "if(attempt<100){setTimeout(function(){initialize(attempt+1);},50);}return;}"
        "mw.config.set("
        + orjson.dumps(config if isinstance(config, dict) else {}).decode().replace("<", "\\u003c")
        + ");mw.loader.using("
        + orjson.dumps(["mediawiki.page.ready", *modules]).decode().replace("<", "\\u003c")
        + ").then(function(){mw.hook('wikipage.content').fire(jQuery('#mw-content-text'));"
        "window.akariPreviewReady=true;},function(){window.akariPreviewPartial=true;"
        "window.akariPreviewReady=true;});})(0);"
    )
    soup.body.append(script)
    warning = bool(parsed.get("parsewarnings") or markup.select(".error,.mw-broken-media,.scribunto-error"))
    return str(soup), warning


def preview_caption(image, invocation, locale, warning=False):
    image = image.convert("RGB")
    image.thumbnail((1600, 3800), PILImage.Resampling.LANCZOS)
    font = ImageFont.truetype(str(noto_sans_demilight_path), 20)
    lines = [
        locale.t(I18NContext("wiki.message.template_preview.heading").key),
        locale.t(I18NContext("wiki.message.template_preview.declaration").key),
        locale.t(
            I18NContext("wiki.message.template_preview.source").key,
            site=invocation.wiki_info.name,
            title=invocation.title,
            context=PREVIEW_CONTEXT,
            time=datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        ),
    ]
    if warning:
        lines.append(locale.t(I18NContext("wiki.message.template_preview.partial").key))
    width = max(720, image.width)
    wrapped = []
    for line in lines:
        current = ""
        for character in line.replace("\n", " "):
            if font.getlength(current + character) > width - 40:
                wrapped.append(current)
                current = ""
            current += character
        wrapped.append(current)
    result = PILImage.new("RGB", (width, image.height + 24 + len(wrapped) * 30), "white")
    result.paste(image, (0, 0))
    draw = ImageDraw.Draw(result)
    draw.rectangle((0, image.height, width, result.height), fill="#eef2f6")
    for index, line in enumerate(wrapped):
        draw.text((20, image.height + 12 + index * 30), line, fill="#253445", font=font)
    return result


async def generate_template_preview(invocation, session):
    if not evaluate_url_policy(invocation.api).allowed:
        raise TemplatePreviewError("not_allowed")
    sender = session.session_info.sender_union_id or session.session_info.sender_id
    if sender in _ACTIVE_SENDERS:
        raise TemplatePreviewError("busy")
    _ACTIVE_SENDERS.add(sender)
    try:
        async with asyncio.timeout(TEMPLATE_PREVIEW_TIMEOUT), _RENDER_SLOTS:
            await check_template_parameters(invocation.source, session)
            async with PreviewRequests(invocation.api, invocation.wiki_info.realurl, invocation.headers) as requests:
                query = await requests.api_json(action="query", prop="info", pageids=invocation.pageid)
                pages = query.get("query", {}).get("pages", [])
                if isinstance(pages, dict):
                    pages = list(pages.values())
                if (
                    not pages
                    or pages[0].get("ns") != 10
                    or pages[0].get("title") != invocation.title
                    or pages[0].get("pageid") != invocation.pageid
                ):
                    raise TemplatePreviewError("missing")
                source = wtp.parse(invocation.source)
                source.templates[0].name = invocation.title
                args = dict(
                    action="parse",
                    text=str(source),
                    title=PREVIEW_CONTEXT,
                    contentmodel="wikitext",
                    preview=1,
                    disableeditsection=1,
                    disabletoc=1,
                    prop="text|headhtml|templates|images|parsewarnings|modules|jsconfigvars|limitreportdata",
                )
                if invocation.wiki_info.default_skin:
                    args["useskin"] = invocation.wiki_info.default_skin
                if invocation.language:
                    args["uselang"] = invocation.language
                response = await requests.api_json(**args)
                parsed = response.get("parse")
                if not isinstance(parsed, dict):
                    raise TemplatePreviewError("unavailable")
                images = parsed.get("images", [])
                if images:
                    resources = await requests.api_json(
                        action="query",
                        prop="imageinfo",
                        iiprop="url",
                        titles="|".join("File:" + name for name in images[:50]),
                    )
                    resource_pages = resources.get("query", {}).get("pages", [])
                    if isinstance(resource_pages, dict):
                        resource_pages = resource_pages.values()
                    for page in resource_pages:
                        for info in page.get("imageinfo", []):
                            if info.get("url"):
                                requests.allow_resource(info["url"])
                document, warning = preview_document(parsed, invocation, session.session_info.locale)
                image, resource_warning = await render_preview_document(document, requests, session.session_info.locale)
                if not evaluate_url_policy(invocation.api).allowed:
                    raise TemplatePreviewError("not_allowed")
                return preview_caption(image, invocation, session.session_info.locale, warning or resource_warning)
    except TimeoutError as error:
        raise TemplatePreviewError("timeout") from error
    finally:
        _ACTIVE_SENDERS.discard(sender)
