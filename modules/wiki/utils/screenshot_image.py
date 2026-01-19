import re
import uuid
from urllib.parse import urljoin

from PIL import Image as PILImage
from akari_bot_webrender.functions.options import SectionScreenshotOptions, LegacyScreenshotOptions
from bs4 import BeautifulSoup, Comment

from core.constants.path import cache_path
from core.logger import Logger
from core.utils.http import get_url
from core.utils.image import cb64imglst
from core.web_render import web_render, ElementScreenshotOptions
from .mapping import infobox_elements


async def generate_screenshot_v2(
    page_link: str,
    section: str = None,
    allow_special_page=False,
    content_mode=False,
    element=None,
    locale: str = "zh_cn",
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
            ElementScreenshotOptions(url=page_link, element=elements_, locale=locale))
        if not imgs:
            Logger.error("[WebRender] Generation Failed.")
            return False
    else:
        Logger.info("[WebRender] Generating section screenshot...")
        imgs = await web_render.section_screenshot(
            SectionScreenshotOptions(url=page_link, section=section, locale=locale))
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
                        fl.append(f"{f}=\"{x.attrs[f]}\"")
                    elif isinstance(x.attrs[f], list):
                        fl.append(f"{f}=\"{" ".join(x.attrs[f])}\"")
                open_file.write(f"<html {" ".join(fl)}>")

            open_file.write("<head>\n")
            for x in soup.find_all(rel="stylesheet"):
                if x.has_attr("href"):
                    get_herf = x.get("href")
                    x.attrs["href"] = re.sub(";", "&", urljoin(link, get_herf))
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
                                open_file.write(
                                    f"<body class=\"{" ".join(x.get("class"))}\">"
                                )

                        for x in soup.find_all("div"):
                            if x.get("id") in ["content", "mw-content-text"]:
                                fl = []
                                for f in x.attrs:
                                    if isinstance(x.attrs[f], str):
                                        fl.append(f"{f}=\"{x.attrs[f]}\"")
                                    elif isinstance(x.attrs[f], list):
                                        fl.append(f"{f}=\"{" ".join(x.attrs[f])}\"")
                                open_file.write(f"<div {" ".join(fl)}>")
                        open_file.write("<div class=\"mw-parser-output\">")

                        for x in soup.find_all("main"):
                            fl = []
                            for f in x.attrs:
                                if isinstance(x.attrs[f], str):
                                    fl.append(f"{f}=\"{x.attrs[f]}\"")
                                elif isinstance(x.attrs[f], list):
                                    fl.append(f"{f}=\"{" ".join(x.attrs[f])}\"")
                            open_file.write(f"<main {" ".join(fl)}>")
                        open_file.write(str(find_diff))
                        w = 2000
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
                            x.attrs["style"] = re.sub(
                                r"url\(/(.*)\)", "url(" + link + "\\1)", x.get("style")
                            )

                    for x in find_infobox.find_all(class_="lazyload"):
                        if x.has_attr("class") and x.has_attr("data-src"):
                            x.attrs["class"] = "image"
                            x.attrs["src"] = x.attrs["data-src"]

                    open_file.write("<div class=\"mw-parser-output\">")

                    open_file.write(str(find_infobox))
                    w = 500
                    open_file.write("</div>")
            else:
                for x in soup.find_all("body"):
                    if x.has_attr("class"):
                        open_file.write(f"<body class=\"{" ".join(x.get("class"))}\">")

                for x in soup.find_all("div"):
                    if x.get("id") in ["content", "mw-content-text"]:
                        fl = []
                        for f in x.attrs:
                            if isinstance(x.attrs[f], str):
                                fl.append(f"{f}=\"{x.attrs[f]}\"")
                            elif isinstance(x.attrs[f], list):
                                fl.append(f"{f}=\"{" ".join(x.attrs[f])}\"")
                        open_file.write(f"<div {" ".join(fl)}>")

                open_file.write("<div class=\"mw-parser-output\">")

                for x in soup.find_all("main"):
                    fl = []
                    for f in x.attrs:
                        if isinstance(x.attrs[f], str):
                            fl.append(f"{f}=\"{x.attrs[f]}\"")
                        elif isinstance(x.attrs[f], list):
                            fl.append(f"{f}=\"{" ".join(x.attrs[f])}\"")
                    open_file.write(f"<main {" ".join(fl)}>")

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
                x.attrs["style"] = re.sub(
                    r"url\(/(.*)\)", "url(" + link + "\\1)", x.get("style")
                )

        for x in soup.find_all(class_="lazyload"):
            if x.has_attr("class") and x.has_attr("data-src"):
                x.attrs["class"] = "image"
                x.attrs["src"] = x.attrs["data-src"]

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
