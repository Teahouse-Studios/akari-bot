import asyncio
from pathlib import Path

import wikitextparser as wtp
from attrs import define
from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader, select_autoescape

from core.builtins.filter import contain_badwords
from core.builtins.message.internal import I18NContext
from core.utils import dirty_check
from core.utils.url_audit import evaluate_url_policy
from .magic import extract_expressions
from .preview_render import PreviewRequests, render_preview_document, render_shell_document
from .wikilib import WikiInfo

MAX_TEMPLATE_LENGTH = 4096
TEMPLATE_PREVIEW_TTL = 300
TEMPLATE_PREVIEW_TIMEOUT = 30
TEMPLATE_SHELL_TIMEOUT = 15
_RENDER_SLOTS = asyncio.Semaphore(2)
_ACTIVE_SENDERS = set()
_TEMPLATE_ENV = Environment(
    loader=FileSystemLoader(Path(__file__).parent),
    autoescape=select_autoescape(["html"]),
)


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


def template_parameters(source: str, *, allow_empty: bool = False) -> list[str]:
    roots = extract_expressions(source)
    if len(source) > MAX_TEMPLATE_LENGTH or len(roots) != 1 or roots[0].span != (0, len(source)):
        raise TemplatePreviewError("invalid")
    root = roots[0]
    if type(root).__name__ != "Template" or (not root.arguments and not allow_empty) or len(root.arguments) > 50:
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
    parameters = template_parameters(source, allow_empty=True)
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


def _template_name(source: str) -> str:
    node = extract_expressions(source)[0]
    return node.name.strip().replace("_", " ").casefold()


def _template_name_variants(source: str) -> set[str]:
    name = _template_name(source)
    return {name, name.split(":", 1)[-1]}


def _canonicalize_source(source: str, invocations: list[TemplateInvocation]) -> str:
    names = {name: item.title for item in invocations for name in _template_name_variants(item.source)}
    parsed = wtp.parse(source)
    roots = {node.span for node in extract_expressions(source)}
    for node in reversed(parsed.templates):
        name = node.name.strip().replace("_", " ").casefold()
        if node.span in roots:
            for variant in (name, name.split(":", 1)[-1]):
                if variant in names:
                    node.name = names[variant]
                    break
    return str(parsed)


def _preview_sources(source: str, invocations: list[TemplateInvocation]) -> list[str]:
    names = {name for item in invocations for name in _template_name_variants(item.source)}
    return [
        str(node)
        for node in extract_expressions(source)
        if type(node).__name__ == "Template" and _template_name_variants(str(node)) & names
    ]


def preview_document(parsed, invocation, locale, *, single_template: bool = False, shell: bool = False):
    def value(key):
        result = parsed.get(key, "")
        return result.get("*", "") if isinstance(result, dict) else result

    body = value("text")
    head = value("headhtml")
    if not isinstance(body, str) or not body.strip() or not isinstance(head, str):
        raise TemplatePreviewError("empty")
    if len((head + body).encode()) > 1024 * 1024:
        raise TemplatePreviewError("too_large")
    soup = BeautifulSoup(head, "html.parser")
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
    if shell and single_template:
        output = markup.select_one(".mw-parser-output") or markup.find(True)
        if output:
            output["data-akari-template-output"] = ""
    for base in soup.find_all("base"):
        base.decompose()
    for tag in soup.find_all("meta"):
        if tag.get("http-equiv", "").lower() == "refresh":
            tag.decompose()
    head_content = list(soup.head.contents) if soup.head else []
    for noscript in [*soup.find_all("noscript"), *markup.find_all("noscript")]:
        for style in noscript.find_all(["style", "link"]):
            head_content.append(style.extract())
    config = parsed.get("jsconfigvars", {})
    modules = parsed.get("modules", [])

    def text(key, **kwargs):
        context = I18NContext("wiki.message.template_preview." + key, **kwargs)
        return locale.t(context.key, locale_failed_prompt=False, **context.kwargs)

    def attributes(tag):
        return {
            key: " ".join(value) if isinstance(value, list) else value
            for key, value in (tag.attrs.items() if tag else [])
            if key in {"class", "lang", "dir"}
        }

    labels = {}
    if single_template:
        labels = {
            key: text("css." + key)
            for key in (
                "element",
                "display",
                "float",
                "position",
                "flex_direction",
                "flex_wrap",
                "grid_columns",
                "grid_rows",
                "grid_auto_flow",
                "justify",
                "align",
                "gap",
                "background",
                "color",
                "font",
                "size",
                "border",
                "radius",
                "shadow",
                "spacing",
            )
        }
    warning = bool(parsed.get("parsewarnings") or markup.select(".error,.mw-broken-media,.scribunto-error"))
    template_name = "template_preview_shell.html" if shell else "template_preview.html"
    document = _TEMPLATE_ENV.get_template(template_name).render(
        html_attrs=attributes(soup.html),
        body_attrs=attributes(soup.body),
        base_url=invocation.wiki_info.realurl.rstrip("/") + "/",
        head="".join(str(item) for item in head_content),
        body=str(markup),
        config=config if isinstance(config, dict) else {},
        modules=["mediawiki.page.ready", *modules],
        single_template=single_template,
        css_labels=labels,
        css_title=text("css.title"),
        watermark=text("watermark", title=invocation.title, status=""),
        watermark_partial=text("watermark", title=invocation.title, status=" · " + text("partial")),
        partial=warning,
    )
    return document, warning


def _template_page_url(invocation: TemplateInvocation) -> str:
    return invocation.wiki_info.realurl.rstrip("/") + "/"


async def _render_template_shell(document, parsed, invocation, locale, requests):
    async with PreviewRequests(invocation.api, invocation.wiki_info.realurl, invocation.headers) as shell_requests:
        shell_requests.origins.update(requests.origins)
        image, _ = await render_shell_document(document, parsed, _template_page_url(invocation), shell_requests, locale)
        return image


async def generate_template_preview(invocation, session, *, source=None, invocations=None):
    if not evaluate_url_policy(invocation.api).allowed:
        raise TemplatePreviewError("not_allowed")
    invocations = list(invocations or [invocation])
    source = source if source is not None else invocation.source
    if not source or len(source) > MAX_TEMPLATE_LENGTH or any(item.api != invocation.api for item in invocations):
        raise TemplatePreviewError("invalid")
    sources = _preview_sources(source, invocations)
    if not sources:
        raise TemplatePreviewError("invalid")
    sender = session.session_info.sender_union_id or session.session_info.sender_id
    if sender in _ACTIVE_SENDERS:
        raise TemplatePreviewError("busy")
    _ACTIVE_SENDERS.add(sender)
    try:
        async with asyncio.timeout(TEMPLATE_PREVIEW_TIMEOUT), _RENDER_SLOTS:
            for template_source in sources:
                await check_template_parameters(template_source, session)
            async with PreviewRequests(invocation.api, invocation.wiki_info.realurl, invocation.headers) as requests:
                query = await requests.api_json(
                    action="query", prop="info", pageids="|".join(str(item.pageid) for item in invocations)
                )
                pages = query.get("query", {}).get("pages", [])
                if isinstance(pages, dict):
                    pages = list(pages.values())
                found = {(page.get("pageid"), page.get("title"), page.get("ns")) for page in pages}
                if any((item.pageid, item.title, 10) not in found for item in invocations):
                    raise TemplatePreviewError("missing")
                args = dict(
                    action="parse",
                    text=_canonicalize_source(source, invocations),
                    title=invocation.title,
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
                document, _ = preview_document(
                    parsed,
                    invocation,
                    session.session_info.locale,
                    single_template=len(sources) == 1,
                )
                shell_document, _ = preview_document(
                    parsed,
                    invocation,
                    session.session_info.locale,
                    single_template=len(sources) == 1,
                    shell=True,
                )
                parse_task = asyncio.create_task(
                    render_preview_document(document, requests, session.session_info.locale)
                )
                shell_task = asyncio.create_task(
                    _render_template_shell(shell_document, parsed, invocation, session.session_info.locale, requests)
                )
                try:
                    try:
                        image = await asyncio.wait_for(shell_task, TEMPLATE_SHELL_TIMEOUT)
                        if image is None:
                            raise TemplatePreviewError("unavailable")
                    except Exception:
                        image, _ = await parse_task
                finally:
                    for task in (shell_task, parse_task):
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(shell_task, parse_task, return_exceptions=True)
                if not evaluate_url_policy(invocation.api).allowed:
                    raise TemplatePreviewError("not_allowed")
                return image
    except TimeoutError as error:
        raise TemplatePreviewError("timeout") from error
    finally:
        _ACTIVE_SENDERS.discard(sender)
