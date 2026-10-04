import asyncio
import re
import uuid
from urllib.parse import parse_qs, urljoin, urlsplit, urlunsplit

from PIL import Image as PILImage
from akari_bot_webrender.functions.options import SectionScreenshotOptions, LegacyScreenshotOptions
from bs4 import BeautifulSoup, Comment

from core.constants.path import cache_path
from core.i18n import Locale
from core.logger import Logger
from core.utils.http import get_url
from core.utils.image import cb64imglst
from core.utils.web_render import web_render, ElementScreenshotOptions
from .diff import DiffError, parse_diff_target, fetch_diff, diff_document
from .mapping import generate_screenshot_v2_blocklist, infobox_elements
from .wikilib import WikiInfo, WikiLib

_ISOLATED_RENDER_CSS = """
html,
body {
    background: #ffffff !important;
}

#mw-content-text,
.mw-parser-output,
.bot-sectionbox {
    background-color: #ffffff !important;
}
"""
_PAGE_RENDER_TIMEOUT = 15


def _styled_document(parsed: dict, page_link: str) -> str | None:
    def value(key):
        result = parsed.get(key)
        return result.get("*") if isinstance(result, dict) else result

    head, text = value("headhtml"), value("text")
    if not isinstance(head, str) or not isinstance(text, str) or not text.strip():
        return None
    soup = BeautifulSoup(head + "</body></html>", "html.parser")
    if not soup.html or not soup.head or not soup.body or not soup.select('link[rel~="stylesheet"][href]'):
        return None
    soup.body.clear()
    content = soup.new_tag("div", id="mw-content-text", attrs={"class": "mw-body-content"})
    content.append(BeautifulSoup(text, "html.parser"))
    soup.body.append(content)
    for tag in soup.find_all(["script", "iframe", "object", "embed", "base"]):
        tag.decompose()
    for tag in soup.find_all(True):
        for attr in list(tag.attrs):
            if attr.lower().startswith("on"):
                del tag[attr]
        if tag.name == "meta" and tag.get("http-equiv", "").lower() == "refresh":
            tag.decompose()
    for noscript in soup.find_all("noscript"):
        for style in noscript.find_all(["style", "link"]):
            soup.head.append(style.extract())
    base = soup.new_tag("base", href=urlunsplit(urlsplit(page_link)._replace(fragment="")))
    soup.head.insert(0, base)
    for image in soup.find_all("img"):
        image.attrs.pop("loading", None)
        if image.get("data-src"):
            image["src"] = urljoin(page_link, image["data-src"])
        if image.get("data-srcset"):
            image["srcset"] = image["data-srcset"]
    return str(soup)


def _parse_target(page_link: str, wiki_info: WikiInfo, title: str | None) -> dict | None:
    query = parse_qs(urlsplit(page_link).query, keep_blank_values=True)
    if set(query) - {"title", "curid"}:
        return None
    title = title or WikiLib._title_from_article_url(page_link, wiki_info.articlepath) or query.get("title", [None])[0]
    if title:
        namespace = title.split(":", 1)[0]
        if ":" in title and (namespace.lower() == "special" or wiki_info.namespaces.get(namespace) == -1):
            return None
        return {"page": title}
    pageid = query.get("curid", [""])[0]
    if pageid.isdecimal():
        return {"pageid": int(pageid)}
    return None


async def generate_screenshot(
    page_link: str,
    wiki_info: WikiInfo,
    title: str | None = None,
    headers: dict | None = None,
    section: str | None = None,
    allow_special_page=False,
    content_mode=False,
    locale: str = "zh_cn",
    diff_data: dict | None = None,
) -> list[PILImage.Image] | bool:
    try:
        diff_target = parse_diff_target(page_link, wiki_info)
    except DiffError:
        return False
    if diff_target is not None:
        if not allow_special_page:
            return False
        try:
            if diff_data is None:
                wiki = WikiLib(wiki_info.api, headers=headers, locale=locale)
                wiki.wiki_info = wiki_info
                async with asyncio.timeout(15):
                    diff_data = await fetch_diff(wiki, diff_target)
            images = await web_render.element_screenshot(
                ElementScreenshotOptions(
                    content=diff_document(diff_data, wiki_info.name, Locale(locale)),
                    element=".wiki-diff",
                    width=1200,
                    counttime=False,
                    locale=locale,
                    stealth=False,
                )
            )
            return cb64imglst(images) if images else False
        except Exception:
            Logger.exception("Failed to render Wiki comparison from API: ")
            return False
    if wiki_info.realurl in generate_screenshot_v2_blocklist:
        return await generate_screenshot_v1(
            wiki_info.realurl, page_link, headers, section=section, allow_special_page=allow_special_page
        )
    # Start the fallback early so a primary-render timeout does not add another full request latency.
    styled_task = asyncio.create_task(
        _generate_styled_api_screenshot(
            page_link,
            wiki_info,
            title=title,
            headers=headers,
            section=section,
            allow_special_page=allow_special_page,
            content_mode=content_mode,
            locale=locale,
        )
    )
    target = _parse_target(page_link, wiki_info, title)
    if not wiki_info.api or not target:
        styled_task.cancel()
        await asyncio.gather(styled_task, return_exceptions=True)
        return await asyncio.wait_for(
            generate_screenshot_v2(
                page_link,
                section=section,
                allow_special_page=allow_special_page,
                content_mode=content_mode,
                locale=locale,
            ),
            timeout=_PAGE_RENDER_TIMEOUT,
        )
    try:
        try:
            page_images = await asyncio.wait_for(
                generate_screenshot_v2(
                    page_link,
                    section=section,
                    allow_special_page=allow_special_page,
                    content_mode=content_mode,
                    locale=locale,
                ),
                timeout=_PAGE_RENDER_TIMEOUT,
            )
        except asyncio.TimeoutError:
            Logger.warning("Wiki page rendering exceeded 15 seconds; using styled API HTML fallback.")
            page_images = False
        except Exception:
            Logger.exception("Failed to render Wiki page; using styled API HTML fallback: ")
            page_images = False
        if page_images:
            styled_task.cancel()
            await asyncio.gather(styled_task, return_exceptions=True)
            return page_images
        return await styled_task
    except asyncio.CancelledError:
        styled_task.cancel()
        await asyncio.gather(styled_task, return_exceptions=True)
        raise


async def _generate_styled_api_screenshot(
    page_link: str,
    wiki_info: WikiInfo,
    *,
    title: str | None,
    headers: dict | None,
    section: str | None,
    allow_special_page: bool,
    content_mode: bool,
    locale: str,
) -> list[PILImage.Image] | bool:
    target = _parse_target(page_link, wiki_info, title)
    if not wiki_info.api or not target:
        return False
    try:
        wiki = WikiLib(wiki_info.api, headers=headers, locale=locale)
        wiki.wiki_info = wiki_info
        async with asyncio.timeout(_PAGE_RENDER_TIMEOUT):
            parse_args = {"action": "parse", "prop": "text|headhtml", "redirects": 1, "formatversion": 2, **target}
            if wiki_info.default_skin:
                parse_args["useskin"] = wiki_info.default_skin
            response = await wiki.get_json(**parse_args)
        content = None
        if not response.get("error") and not response.get("warnings"):
            content = _styled_document(response.get("parse", {}), page_link)
        if not content:
            return False
        return await generate_screenshot_v2(
            page_link,
            section=section,
            allow_special_page=allow_special_page,
            content_mode=content_mode,
            locale=locale,
            content=content,
        )
    except asyncio.CancelledError:
        raise
    except Exception:
        Logger.exception("Failed to render styled Wiki API HTML fallback: ")
        return False


async def generate_screenshot_v2(
    page_link: str,
    section: str | None = None,
    allow_special_page=False,
    content_mode=False,
    element=None,
    locale: str = "zh_cn",
    content: str | None = None,
) -> list[PILImage.Image] | bool:
    elements_ = infobox_elements.copy()
    if element and isinstance(element, list):
        elements_ += element
    if not section:
        if allow_special_page and content_mode:
            elements_.insert(0, ".mw-body-content")
        if allow_special_page and not content_mode:
            elements_.insert(0, ".diff")
        Logger.info("[WebRender] Generating element screenshot...")
        imgs = await web_render.element_screenshot(
            ElementScreenshotOptions(
                url=None if content else page_link,
                content=content,
                css=_ISOLATED_RENDER_CSS if content else None,
                element=elements_,
                locale=locale,
                stealth=False,
            )
        )
        if not imgs:
            Logger.error("[WebRender] Generation Failed.")
            return False
    else:
        Logger.info("[WebRender] Generating section screenshot...")
        imgs = await web_render.section_screenshot(
            SectionScreenshotOptions(
                url=None if content else page_link,
                content=content,
                css=_ISOLATED_RENDER_CSS if content else None,
                section=section,
                locale=locale,
                stealth=False,
            )
        )
        if not imgs:
            Logger.error("[WebRender] Generation Failed.")
            return False
    return cb64imglst(imgs)


async def generate_screenshot_v1(
    link, page_link, headers, section=None, allow_special_page=False
) -> list[PILImage.Image] | bool:
    try:
        Logger.info("Starting find infobox/section..")
        if link[-1] != "/":
            link += "/"
        try:
            html = await get_url(page_link, 200, headers=headers, timeout=20)
        except Exception:
            Logger.exception()
            return False
        soup = BeautifulSoup(html, "html.parser")
        pagename = uuid.uuid4()
        url = cache_path / f"{pagename}.html"
        if url.exists():
            url.unlink()
        Logger.info("Downloaded raw.")

        def join_url(base, target):
            target = target.split(" ")
            targetlist = []
            for x in target:
                if x.find("/") != -1:
                    x = urljoin(base, x)
                    targetlist.append(x)
                else:
                    targetlist.append(x)
            target = " ".join(targetlist)
            return target

        with open(url, "a", encoding="utf-8") as open_file:
            open_file.write("<!DOCTYPE html>\n")
            for x in soup.find_all("html"):
                fl = []
                for f in x.attrs:
                    if isinstance(x.attrs[f], str):
                        fl.append(f'{f}="{x.attrs[f]}"')
                    elif isinstance(x.attrs[f], list):
                        fl.append(f'{f}="{" ".join(x.attrs[f])}"')
                open_file.write(f"<html {' '.join(fl)}>")

            open_file.write("<head>\n")
            for x in soup.find_all(rel="stylesheet"):
                if x.has_attr("href"):
                    get_href = x.get("href")
                    x.attrs["href"] = re.sub(";", "&", urljoin(link, get_href))
                open_file.write(str(x))

            for x in soup.find_all():
                if x.has_attr("href"):
                    x.attrs["href"] = re.sub(";", "&", urljoin(link, x.get("href")))
            open_file.write("</head>")

            for x in soup.find_all("style"):
                open_file.write(str(x))

            if not section:
                find_diff = None
                if allow_special_page:
                    find_diff = soup.find("table", class_=re.compile("diff"))
                    if find_diff:
                        Logger.info("Found diff...")
                        for x in soup.find_all("body"):
                            if x.has_attr("class"):
                                open_file.write(f'<body class="{" ".join(x.get("class"))}">')

                        for x in soup.find_all("div"):
                            if x.get("id") in ["content", "mw-content-text"]:
                                fl = []
                                for f in x.attrs:
                                    if isinstance(x.attrs[f], str):
                                        fl.append(f'{f}="{x.attrs[f]}"')
                                    elif isinstance(x.attrs[f], list):
                                        fl.append(f'{f}="{" ".join(x.attrs[f])}"')
                                open_file.write(f"<div {' '.join(fl)}>")
                        open_file.write('<div class="mw-parser-output">')

                        for x in soup.find_all("main"):
                            fl = []
                            for f in x.attrs:
                                if isinstance(x.attrs[f], str):
                                    fl.append(f'{f}="{x.attrs[f]}"')
                                elif isinstance(x.attrs[f], list):
                                    fl.append(f'{f}="{" ".join(x.attrs[f])}"')
                            open_file.write(f"<main {' '.join(fl)}>")
                        open_file.write(str(find_diff))
                if not find_diff:
                    infoboxes = infobox_elements.copy()
                    find_infobox = None
                    for i in infoboxes:
                        find_infobox = soup.find(class_=i[1:])
                        if find_infobox:
                            break
                    if not find_infobox:
                        Logger.info("Found nothing...")
                        return False
                    Logger.info("Found infobox...")

                    for x in find_infobox.find_all(["a", "img", "span"]):
                        if x.has_attr("href"):
                            x.attrs["href"] = join_url(link, x.get("href"))
                        if x.has_attr("src"):
                            x.attrs["src"] = join_url(link, x.get("src"))
                        if x.has_attr("srcset"):
                            x.attrs["srcset"] = join_url(link, x.get("srcset"))
                        if x.has_attr("style"):
                            x.attrs["style"] = re.sub(r"url\(/(.*)\)", "url(" + link + "\\1)", x.get("style"))

                    for x in find_infobox.find_all(class_="lazyload"):
                        if x.has_attr("class") and x.has_attr("data-src"):
                            x.attrs["class"] = "image"
                            x.attrs["src"] = x.attrs["data-src"]

                    open_file.write('<div class="mw-parser-output">')

                    open_file.write(str(find_infobox))
                    open_file.write("</div>")
            else:
                for x in soup.find_all("body"):
                    if x.has_attr("class"):
                        open_file.write(f'<body class="{" ".join(x.get("class"))}">')

                for x in soup.find_all("div"):
                    if x.get("id") in ["content", "mw-content-text"]:
                        fl = []
                        for f in x.attrs:
                            if isinstance(x.attrs[f], str):
                                fl.append(f'{f}="{x.attrs[f]}"')
                            elif isinstance(x.attrs[f], list):
                                fl.append(f'{f}="{" ".join(x.attrs[f])}"')
                        open_file.write(f"<div {' '.join(fl)}>")

                open_file.write('<div class="mw-parser-output">')

                for x in soup.find_all("main"):
                    fl = []
                    for f in x.attrs:
                        if isinstance(x.attrs[f], str):
                            fl.append(f'{f}="{x.attrs[f]}"')
                        elif isinstance(x.attrs[f], list):
                            fl.append(f'{f}="{" ".join(x.attrs[f])}"')
                    open_file.write(f"<main {' '.join(fl)}>")

                def is_comment(e):
                    return isinstance(e, Comment)

                to_remove = soup.find_all(text=is_comment)
                for element in to_remove:
                    element.extract()
                selected = False
                x = None
                hx = ["h1", "h2", "h3", "h4", "h5", "h6"]
                selected_hx = None
                for h in hx:
                    if selected:
                        break
                    for x in soup.find_all(h):
                        for y in x.find_all("span", id=section):
                            if y != "":
                                selected = True
                                selected_hx = h
                                break
                        if selected:
                            break
                if not selected:
                    Logger.info("Nothing found.")
                    return False
                Logger.info("Found section...")
                open_file.write(str(x))
                b = x
                bl = []
                while True:
                    b = b.next_sibling
                    if not b:
                        break

                    if b.name == selected_hx:
                        break
                    if b.name in hx and hx.index(selected_hx) >= hx.index(b.name):
                        break
                    if b not in bl:
                        bl.append(str(b))
                open_file.write("".join(bl))

        with open(url, "r", encoding="utf-8") as open_file:
            soup = BeautifulSoup(open_file.read(), "html.parser")

        for x in soup.find_all(["a", "img", "span"]):
            if x.has_attr("href"):
                x.attrs["href"] = join_url(link, x.get("href"))
            if x.has_attr("src"):
                x.attrs["src"] = join_url(link, x.get("src"))
            if x.has_attr("srcset"):
                x.attrs["srcset"] = join_url(link, x.get("srcset"))
            if x.has_attr("style"):
                x.attrs["style"] = re.sub(r"url\(/(.*)\)", "url(" + link + "\\1)", x.get("style"))

        for x in soup.find_all(class_="lazyload"):
            if x.has_attr("class") and x.has_attr("data-src"):
                x.attrs["class"] = "image"
                x.attrs["src"] = x.attrs["data-src"]

        with open(url, "w", encoding="utf-8") as open_file:
            open_file.write(str(soup))
            w = 1000
            open_file.write("</div></body>")

        with open(url, "r", encoding="utf-8") as read_file:
            html = {"content": read_file.read(), "width": w, "mw": True}

        Logger.info("Start rendering...")
        imgs_data = await web_render.legacy_screenshot(LegacyScreenshotOptions(**html))
        return cb64imglst(imgs_data)
    except Exception:
        Logger.exception()
        return False
