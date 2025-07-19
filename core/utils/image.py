import base64
from io import BytesIO
from typing import List, Optional, Union

from PIL import Image as PILImage
from jinja2 import FileSystemLoader, Environment

from core.builtins.message.chain import MessageChain, MessageNodes
from core.builtins.message.elements import PlainElement, ImageElement, EmbedElement
from core.builtins.session.info import SessionInfo, FetchedSessionInfo
from core.builtins.session.internal import MessageSession
from core.config import Config
from core.constants.path import templates_path
from core.logger import Logger
from core.utils.cache import random_cache_path
from core.utils.web_render import web_render, ElementScreenshotOptions

env = Environment(loader=FileSystemLoader(templates_path), autoescape=True, enable_async=True)
use_font_mirror = Config("use_font_mirror", False, bool)


async def image_split(i: ImageElement) -> List[ImageElement]:
    i = PILImage.open(await i.get())
    iw, ih = i.size
    if ih <= 1500:
        return [ImageElement.assign(i)]
    _h = 0
    i_list = []
    for _ in range((ih // 1500) + 1):
        if _h + 1500 > ih:
            crop_h = ih
        else:
            crop_h = _h + 1500
        i_list.append(ImageElement.assign(i.crop((0, _h, iw, crop_h))))
        _h = crop_h
    return i_list


def get_fontsize(font, text):
    left, top, right, bottom = font.getbbox(text)
    return right - left, bottom - top


def cb64imglst(b64imglst: List[str], bot_img=False) -> List[Union[PILImage.Image, ImageElement]]:
    """转换base64编码的图片列表。

    :param b64imglst: base64编码的图片列表。
    :param bot_img: 是否将图片转换为机器人 ImageElement 对象。
    :return: PIL Image 或机器人 Image 对象列表。
    """
    img_lst = []
    for x in b64imglst:
        b = base64.b64decode(x)
        bio = BytesIO(b)
        bimg = PILImage.open(bio)
        if bot_img:
            bimg = ImageElement.assign(bimg)
        img_lst.append(bimg)
    return img_lst


save_source = True


async def msgnode2image(message_node: MessageNodes,
                        session: Optional[Union[MessageSession, SessionInfo, FetchedSessionInfo]] = None,
                        use_local: bool = True):
    new_chain_list = []
    for m in message_node.values:
        for x in m.as_sendable(session):
            new_chain_list.append(x)
    message_chain = MessageChain.assign(new_chain_list)
    return await msgchain2image(message_chain, session)


async def msgchain2image(message_chain: Union[List, MessageChain],
                         session: Optional[Union[MessageSession, SessionInfo, FetchedSessionInfo]] = None) -> Union[
        List[ImageElement], bool]:
    """使用WebRender将消息链转换为图片。

    :param message_chain: 消息链或消息链列表。
    :param session: 消息会话信息，用于转换消息链为可发送格式时使用。
    :return: 机器人 Image 对象。
    """

    if isinstance(message_chain, List):
        message_chain = MessageChain.assign(message_chain)

    if isinstance(session, MessageSession):
        session = session.session_info
    message_list = message_chain.as_sendable(session)
    for m in message_list:
        if isinstance(m, ImageElement):
            await m.get_base64(mime=True)
        elif isinstance(m, EmbedElement):
            if m.image is not None:
                await m.image.get_base64(mime=True)
    title = 'Message List'
    if session:
        title = session.locale.t("message.list")

    html_content = await env.get_template("msgchain_to_image.html").render_async(title=title,
                                                                                 message_list=message_list,
                                                                                 isinstance=isinstance,
                                                                                 PlainElement=PlainElement,
                                                                                 ImageElement=ImageElement,
                                                                                 EmbedElement=EmbedElement,
                                                                                 use_font_mirror=use_font_mirror, )
    fname = f"{random_cache_path()}.html"
    with open(fname, "w", encoding="utf-8") as fi:
        fi.write(html_content)

    Logger.info("[WebRender] Converting message chain...")
    pic_list = await web_render.element_screenshot(ElementScreenshotOptions(content=html_content, element=[".botbox"]))
    if not pic_list:
        Logger.exception("[WebRender] Generation Failed.")
        return False

    return cb64imglst(pic_list, bot_img=True)


async def svg_render(file_path: str) -> Union[List[ImageElement], bool]:
    """使用WebRender渲染svg文件。

    :param file_path: svg文件路径。
    :return: 机器人 Image 对象。
    """

    with open(file_path, "r", encoding="utf-8") as file:
        svg_content = file.read()

    html_content = await env.get_template("svg_template.html").render_async(svg=svg_content,
                                                                            use_font_mirror=use_font_mirror)

    fname = f"{random_cache_path()}.html"
    with open(fname, "w", encoding="utf-8") as fi:
        fi.write(html_content)

    pic_list = await web_render.element_screenshot(
        ElementScreenshotOptions(content=html_content, element=[".botbox"], counttime=False, output_type='png'))
    if not pic_list:
        Logger.exception("[WebRender] Generation Failed.")
        return False

    return cb64imglst(pic_list, bot_img=True)
