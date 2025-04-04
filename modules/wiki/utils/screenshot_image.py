import base64
import os
import re
import traceback
import uuid
from io import BytesIO
from typing import Union, List
from urllib.parse import urljoin

import httpx
import orjson as json
from PIL import Image as PILImage
from bs4 import BeautifulSoup, Comment

from core.constants.info import Info
from core.constants.path import cache_path
from core.logger import Logger
from core.utils.http import download
from core.utils.web_render import webrender
from .mapping import infobox_elements


async def generate_screenshot_v2(
    page_link: str,
    section: str = None,
    allow_special_page=False,
    content_mode=False,
    use_local=True,
    element=None,
) -> Union[List[PILImage], bool]:
    elements_ = infobox_elements.copy()
    if element and isinstance(element, List):
        elements_ += element
    if not Info.web_render_status:
        return False
    if not Info.web_render_local_status:
        use_local = False
    if not section:
        if allow_special_page and content_mode:
            elements_.insert(0, ".mw-body-content")
        if allow_special_page and not content_mode:
            elements_.insert(0, ".diff")
        Logger.info("[WebRender] Generating element screenshot...")
        try:
            img = await download(
                webrender("element_screenshot", use_local=use_local),
                status_code=200,
                headers={"Content-Type": "application/json"},
                method="POST",
                post_data=json.dumps({"url": page_link, "element": elements_}),
                attempt=1,
                timeout=30,
                request_private_ip=True,
            )
        except Exception:
            if use_local:
                return await generate_screenshot_v2(
                    page_link,
                    section,
                    allow_special_page,
                    content_mode,
                    use_local=False,
                )
            Logger.error("[WebRender] Generation Failed.")
            return False
    else:
        Logger.info("[WebRender] Generating section screenshot...")
        try:
            section = section.replace(" ", "_")
            img = await download(
                webrender("section_screenshot", use_local=use_local),
                status_code=200,
                headers={"Content-Type": "application/json"},
                method="POST",
                post_data=json.dumps({"url": page_link, "section": section}),
                attempt=1,
                timeout=30,
                request_private_ip=True,
            )
        except Exception:
            if use_local:
                return await generate_screenshot_v2(
                    page_link,
                    section,
                    allow_special_page,
                    content_mode,
                    use_local=False,
                )
            Logger.error("[WebRender] Generation Failed.")
            return False
    with open(img) as read:
        load_img = json.loads(read.read())
    img_lst = []
    for x in load_img:
        b = base64.b64decode(x)
        bio = BytesIO(b)
        bimg = PILImage.open(bio)
        img_lst.append(bimg)
    return img_lst


async def generate_screenshot_v1(
    link, page_link, headers, use_local=True, section=None, allow_special_page=False
) -> Union[List[PILImage], bool]:
    if not Info.web_render_status:
        return False
    if not Info.web_render_local_status:
        use_local = False
    try:
        Logger.info("Starting find infobox/section..")
        if link[-1] != "/":
            link += "/"
        try:
            async with httpx.AsyncClient(headers=headers) as client:
                resp = await client.get(page_link, timeout=20)
                html = resp.text
        except Exception:
            Logger.error(traceback.format_exc())
            return False
        soup = BeautifulSoup(html, "html.parser")
        pagename = uuid.uuid4()
        url = os.path.join(cache_path, f"{pagename}.html")
        if os.path.exists(url):
            os.remove(url)
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
        img_lst = []
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    webrender(),
                    headers={
                        "Content-Type": "application/json",
                    },
                    data=json.dumps(html),
                )
                if resp.status_code != 200:
                    Logger.error(f"Failed to render: {resp.text}")
                    return False
                imgs_data = json.loads(resp.text)
                for img in imgs_data:
                    b = base64.b64decode(img)
                    bio = BytesIO(b)
                    bimg = PILImage.open(bio)
                    img_lst.append(bimg)

        except httpx.RequestError as e:
            Logger.error(f"Request error: {e}")
            if use_local:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        webrender(use_local=False),
                        headers={
                            "Content-Type": "application/json",
                        },
                        data=json.dumps(html),
                    )
                    if resp.status_code != 200:
                        Logger.error(f"Failed to render: {resp.text}")
                        return False
                    imgs_data = json.loads(resp.text)
                    for img in imgs_data:
                        b = base64.b64decode(img)
                        bio = BytesIO(b)
                        bimg = PILImage.open(bio)
                        img_lst.append(bimg)

        return img_lst
    except Exception:
        Logger.error(traceback.format_exc())
        return False
