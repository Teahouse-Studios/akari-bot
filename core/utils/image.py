import base64
from io import BytesIO
from typing import List, Optional, Union

import filetype as ft
import orjson as json
from PIL import Image as PILImage
from aiofile import async_open
from jinja2 import FileSystemLoader, Environment

from core.builtins import Info, MessageSession, MessageChain, Image
from core.builtins.message.elements import MessageElement, PlainElement, ImageElement, VoiceElement, EmbedElement
from core.constants.path import templates_path
from core.logger import Logger
from core.utils.cache import random_cache_path
from core.utils.http import download
from core.utils.web_render import webrender

env = Environment(loader=FileSystemLoader(templates_path), autoescape=True)


async def image_split(i: ImageElement) -> List[ImageElement]:
    i = PILImage.open(await i.get())
    iw, ih = i.size
    if ih <= 1500:
        return [Image(i)]
    _h = 0
    i_list = []
    for _ in range((ih // 1500) + 1):
        if _h + 1500 > ih:
            crop_h = ih
        else:
            crop_h = _h + 1500
        i_list.append(Image(i.crop((0, _h, iw, crop_h))))
        _h = crop_h
    return i_list


def get_fontsize(font, text):
    left, top, right, bottom = font.getbbox(text)
    return right - left, bottom - top


save_source = True


async def msgchain2image(message_chain: Union[MessageChain, str, list, MessageElement],
                         msg: Optional[MessageSession] = None) -> Union[List[PILImage.Image], bool]:
    """使用WebRender将消息链转换为图片。

    :param message_chain: 消息链或消息链列表。
    :return: 图片的PIL对象列表。
    """
    if not Info.web_render_status:
        return False

    lst = []
    message_chain = MessageChain(message_chain)
    for m in message_chain.as_sendable(msg=msg, embed=False):
        if isinstance(m, PlainElement):
            lst.append("<div>" + m.text.replace("\n", "<br>") + "</div>")
        elif isinstance(m, ImageElement):
            async with async_open(await m.get(), "rb") as fi:
                data = await fi.read()
                try:
                    ftt = ft.match(data)
                    lst.append(f"<img src=\"data:{ftt.mime};base64,{
                               (base64.encodebytes(data)).decode("utf-8")}\" width=\"720\" />")
                except Exception:
                    Logger.exception()
        elif isinstance(m, VoiceElement):
            lst.append("<div>[Voice]</div>")
        elif isinstance(m, EmbedElement):
            lst.append("<div>[Embed]</div>")

    html_content = env.get_template("msgchain_to_image.html").render(content="\n".join(lst))
    fname = f"{random_cache_path()}.html"
    with open(fname, "w", encoding="utf-8") as fi:
        fi.write(html_content)

    d = {"content": html_content, "element": ".botbox"}
    html_ = json.dumps(d)

    Logger.info("[WebRender] Converting message chain...")
    try:
        pic = await download(webrender("element_screenshot"),
                             status_code=200,
                             headers={"Content-Type": "application/json"},
                             method="POST",
                             post_data=html_,
                             attempt=1,
                             timeout=30,
                             request_private_ip=True
                             )
    except Exception:
        Logger.exception("[WebRender] Generation Failed.")
        return False

    with open(pic, "rb") as read:
        load_img = json.loads(read.read())
    img_lst = []
    for x in load_img:
        b = base64.b64decode(x)
        bio = BytesIO(b)
        bimg = PILImage.open(bio)
        img_lst.append(bimg)

    return img_lst


async def svg_render(file_path: str) -> Union[List[PILImage.Image], bool]:
    """使用WebRender渲染svg文件。

    :param file_path: svg文件路径。
    :return: 图片的PIL对象。
    """
    if not Info.web_render_status:
        return False

    with open(file_path, "r", encoding="utf-8") as file:
        svg_content = file.read()

    html_content = env.get_template("svg_template.html").render(svg=svg_content)

    fname = f"{random_cache_path()}.html"
    with open(fname, "w", encoding="utf-8") as fi:
        fi.write(html_content)

    d = {"content": html_content, "element": ".botbox", "counttime": False}
    html_ = json.dumps(d)

    try:
        pic = await download(webrender("element_screenshot"),
                             status_code=200,
                             headers={"Content-Type": "application/json"},
                             method="POST",
                             post_data=html_,
                             attempt=1,
                             timeout=30,
                             request_private_ip=True
                             )
    except Exception:
        Logger.exception("[WebRender] Generation Failed.")
        return False

    with open(pic, "rb") as read:
        load_img = json.loads(read.read())

    img_lst = []
    for x in load_img:
        b = base64.b64decode(x)
        bio = BytesIO(b)
        bimg = PILImage.open(bio)
        img_lst.append(bimg)

    return img_lst
