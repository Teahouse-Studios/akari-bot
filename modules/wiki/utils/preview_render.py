import base64
import math
import re
import uuid
from io import BytesIO
from urllib.parse import parse_qs, urljoin, urlsplit, urlunsplit

import httpx
import orjson
from bs4 import BeautifulSoup
from PIL import Image as PILImage

from core.config.network import proxy, ssl_verify
from core.config.base import CoreConfig
from core.utils.http import private_ip_check
from core.utils.url_audit import evaluate_url_policy
from core.utils.web_render import web_render, ElementScreenshotOptions

_MAX_RESOURCE_BYTES = 10 * 1024 * 1024
_MAX_PIXELS = 12_000_000
_CSS_URL = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.I)
_CSS_IMPORT = re.compile(r"@import\s+(['\"])(.*?)\1", re.I)


def _origin(url):
    parsed = urlsplit(url)
    scheme = parsed.scheme.lower()
    return scheme, parsed.hostname, parsed.port or (443 if scheme == "https" else 80)


class PreviewRequests:
    def __init__(self, api, site, headers):
        self.api = api
        self.site = site
        self.origins = {_origin(api), _origin(site)}
        self.script_paths = {(urlsplit(api).netloc, urljoin(urlsplit(api).path, "load.php"))}
        self.total_bytes = 0
        self.cache = {}
        self.warning = False
        self.failures = []
        self.headers = {
            key: value for key, value in headers.items() if key.lower() in {"user-agent", "accept-language"}
        }
        if not any(key.lower() == "user-agent" for key in self.headers):
            self.headers["User-Agent"] = f"AkariBot/1.0 (+{CoreConfig.repo_url})"

    async def __aenter__(self):
        self.client = httpx.AsyncClient(
            proxy=proxy, verify=ssl_verify, timeout=8, headers=self.headers, follow_redirects=False
        )
        return self

    async def __aexit__(self, *_):
        await self.client.aclose()

    def allow_resource(self, url):
        self.origins.add(_origin(urljoin(self.site, url)))

    def resource_allowed(self, url, kind):
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password:
            return False
        if _origin(url) not in self.origins or evaluate_url_policy(url).blocked:
            return False
        action = parse_qs(parsed.query).get("action", [])
        if action and action != ["query"] and action != ["parse"]:
            return False
        if kind == "script":
            return (parsed.netloc, parsed.path) in self.script_paths
        return kind in {"stylesheet", "image", "font"}

    async def fetch(self, url, kind, *, params=None):
        endpoint = url
        url = str(httpx.URL(url, params=params)) if params is not None else url
        key = (url, kind)
        if key in self.cache:
            return self.cache[key]
        original = url
        body = params if kind == "api" and params and len(url) > 2000 else None
        if body:
            url = endpoint
        for _ in range(5):
            if kind == "api":
                endpoint = urlunsplit(urlsplit(url)._replace(query="", fragment=""))
                if not evaluate_url_policy(endpoint).allowed or evaluate_url_policy(url).blocked:
                    raise ValueError("Wiki API is not allowed")
            elif not self.resource_allowed(url, kind):
                raise ValueError("Preview resource is not allowed")
            await private_ip_check(url)
            async with self.client.stream(
                "POST" if body else "GET",
                url,
                data=body,
                headers={"Promise-Non-Write-API-Action": "true"} if body else None,
            ) as response:
                if response.is_redirect:
                    url = urljoin(url, response.headers["location"])
                    continue
                response.raise_for_status()
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    self.total_bytes += len(chunk)
                    if self.total_bytes > _MAX_RESOURCE_BYTES:
                        raise ValueError("Preview resource budget exceeded")
                    data.extend(chunk)
                content_type = response.headers.get("content-type", "application/octet-stream")
            result = (bytes(data), content_type, url)
            self.cache[(original, kind)] = result
            if kind == "stylesheet":
                css = result[0].decode("utf-8", errors="replace")
                for _, target in _CSS_URL.findall(css) + _CSS_IMPORT.findall(css):
                    if not target.startswith(("data:", "#")):
                        self.allow_resource(urljoin(url, target))
            return result
        raise ValueError("Too many preview resource redirects")

    async def api_json(self, **params):
        if params.get("action") not in {"query", "parse"}:
            raise ValueError("Only read-only preview actions are supported")
        data, _, _ = await self.fetch(self.api, "api", params={**params, "format": "json", "formatversion": 2})
        response = orjson.loads(data)
        if not isinstance(response, dict) or response.get("error"):
            raise ValueError("Invalid Wiki preview response")
        return response


def _document_resources(document, requests):
    soup = BeautifulSoup(document, "html.parser")
    for tag in soup.head.find_all("link", href=True):
        if "stylesheet" in tag.get("rel", []):
            requests.allow_resource(tag["href"])
    for tag in soup.head.find_all("script", src=True):
        target = urlsplit(urljoin(requests.site, tag["src"]))
        requests.allow_resource(tag["src"])
        requests.script_paths.add((target.netloc, target.path))
    return soup


async def _local_render(document, requests, locale):
    browser = web_render.browser.browser
    context = await browser.new_context(
        viewport={"width": 960, "height": 800}, locale=locale.locale.replace("_", "-"), service_workers="block"
    )
    try:
        document_url = requests.site.rstrip("/") + "/__akari_template_preview__/" + uuid.uuid4().hex
        document_served = False

        async def route_request(route):
            nonlocal document_served
            request = route.request
            if request.url == document_url and request.is_navigation_request() and not document_served:
                document_served = True
                await route.fulfill(body=document, content_type="text/html; charset=utf-8")
                return
            if request.method != "GET" or request.is_navigation_request():
                await route.abort()
                return
            try:
                data, content_type, _ = await requests.fetch(request.url, request.resource_type)
                await route.fulfill(body=data, content_type=content_type)
            except Exception as error:
                requests.warning = True
                requests.failures.append(type(error).__name__)
                await route.abort()

        await context.route("**/*", route_request)
        page = await context.new_page()
        page.on("pageerror", lambda error: requests.failures.append(str(error)[:200]))
        # 本地应答的虚拟 URL 为站点模块提供正确 origin，不向 Wiki 创建或请求页面。
        await page.goto(document_url, wait_until="networkidle", timeout=15000)
        try:
            await page.wait_for_function("window.akariPreviewReady === true", timeout=6000)
            if await page.evaluate("Boolean(window.akariPreviewPartial)"):
                requests.warning = True
        except Exception:
            requests.warning = True
            requests.failures.append("Module initialization timed out")
        await page.evaluate(
            "async () => {await document.fonts.ready; await Promise.all(Array.from(document.images, "
            "img => img.decode().catch(() => {window.akariPreviewResourcePartial=true;})));}"
        )
        if await page.evaluate("Boolean(window.akariPreviewResourcePartial)"):
            requests.warning = True
        content = page.locator("body > #mw-content-text")
        await content.evaluate(
            "(element, partial) => {if (partial) element.dataset.previewPartial = 'true';"
            "if (typeof window.akariFillCssPanel === 'function') window.akariFillCssPanel();}",
            requests.warning,
        )
        measure = """element => {
            const bounds = element.getBoundingClientRect();
            return {x: Math.max(0,bounds.x), y: Math.max(0,bounds.y),
                width:Math.max(bounds.width,element.scrollWidth),
                height:Math.max(bounds.height,element.scrollHeight)};
        }"""
        size = await content.evaluate(measure)
        width, height = math.ceil(size["width"]), math.ceil(size["height"])
        if width < 1 or height < 1 or width * height > _MAX_PIXELS or width > 4096 or height > 16000:
            raise ValueError("Preview dimensions exceed limits")
        if width > 960:
            await page.set_viewport_size({"width": width, "height": 800})
            size = await content.evaluate(measure)
            width, height = math.ceil(size["width"]), math.ceil(size["height"])
            if width * height > _MAX_PIXELS:
                raise ValueError("Preview dimensions exceed limits")
        await content.evaluate(
            "(element, bounds) => {"
            "element.style.setProperty('--akari-watermark-width', bounds.width + 'px');"
            "element.style.setProperty('--akari-watermark-height', bounds.height + 'px');}",
            {"width": width, "height": height},
        )
        data = await page.screenshot(
            type="png", full_page=True, clip={"x": size["x"], "y": size["y"], "width": width, "height": height}
        )
        image = PILImage.open(BytesIO(data))
        image.load()
        return image
    finally:
        await context.close()


async def _inline_css(css, base, requests, depth=0):
    if depth > 5:
        raise ValueError("Preview stylesheet nesting exceeds limits")
    for match in list(_CSS_IMPORT.finditer(css)):
        target = urljoin(base, match[2])
        data, _, final = await requests.fetch(target, "stylesheet")
        replacement = await _inline_css(data.decode("utf-8", errors="replace"), final, requests, depth + 1)
        css = css.replace(
            match[0], '@import url("data:text/css;base64,' + base64.b64encode(replacement.encode()).decode() + '")'
        )
    for match in list(_CSS_URL.finditer(css)):
        target = match[2]
        if target.startswith(("data:", "#")):
            continue
        target = urljoin(base, target)
        try:
            kind = "stylesheet" if target.lower().split("?", 1)[0].endswith(".css") else "image"
            data, content_type, final = await requests.fetch(target, kind)
            if "text/css" in content_type:
                data = (await _inline_css(data.decode("utf-8", errors="replace"), final, requests, depth + 1)).encode()
            replacement = "data:" + content_type.split(";", 1)[0] + ";base64," + base64.b64encode(data).decode()
            css = css.replace(match[0], 'url("' + replacement + '")')
        except Exception:
            requests.warning = True
            css = css.replace(match[0], 'url("")')
    return css


async def _remote_render(soup, requests, locale):
    # 远程接口不支持请求路由，所有资源须先受控下载并内联，CSP 禁止后续联网。
    requests.warning = True
    content = soup.select_one("body > #mw-content-text")
    content["data-preview-partial"] = "true"
    for script in soup.find_all("script"):
        if script.get("data-akari-preview-script") != "css-panel":
            script.decompose()
    for tag in list(soup.head.find_all("link")):
        if "stylesheet" in tag.get("rel", []) and tag.get("href"):
            try:
                data, _, final = await requests.fetch(urljoin(requests.site, tag["href"]), "stylesheet")
                style = soup.new_tag("style")
                style.string = await _inline_css(data.decode("utf-8", errors="replace"), final, requests)
                tag.replace_with(style)
            except Exception:
                requests.warning = True
                tag.decompose()
        else:
            tag.decompose()
    for tag in soup.find_all("style"):
        tag.string = await _inline_css(str(tag.string or ""), requests.site, requests)
    for tag in soup.find_all(style=True):
        tag["style"] = await _inline_css(tag["style"], requests.site, requests)
    for tag in soup.find_all(["img", "source"]):
        tag.attrs.pop("srcset", None)
        if tag.get("src") and not tag["src"].startswith("data:"):
            try:
                data, content_type, _ = await requests.fetch(urljoin(requests.site, tag["src"]), "image")
                tag["src"] = "data:" + content_type.split(";", 1)[0] + ";base64," + base64.b64encode(data).decode()
            except Exception:
                requests.warning = True
                tag.attrs.pop("src", None)
    soup.head.insert(
        0,
        soup.new_tag(
            "meta",
            attrs={
                "http-equiv": "Content-Security-Policy",
                "content": "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline' data:; img-src data:; font-src data:; base-uri 'none'",
            },
        ),
    )
    images = await web_render.element_screenshot(
        ElementScreenshotOptions(
            content=str(soup),
            element="body > #mw-content-text",
            width=960,
            counttime=False,
            locale=locale.locale,
            stealth=False,
        )
    )
    if not images or len(images) != 1:
        raise ValueError("Remote preview must return a single image")
    image = PILImage.open(BytesIO(base64.b64decode(images[0])))
    if image.width * image.height > _MAX_PIXELS:
        raise ValueError("Remote preview dimensions exceed limits")
    image.load()
    return image


async def render_preview_document(document, requests, locale):
    soup = _document_resources(document, requests)
    soup.head.insert(
        0,
        soup.new_tag(
            "meta",
            attrs={
                "http-equiv": "Content-Security-Policy",
                "content": "connect-src 'none'; frame-src 'none'; object-src 'none'; form-action 'none'",
            },
        ),
    )
    if not web_render.remote_only and await web_render.browser.check_status():
        image = await _local_render(str(soup), requests, locale)
    else:
        image = await _remote_render(soup, requests, locale)
    return image, requests.warning
