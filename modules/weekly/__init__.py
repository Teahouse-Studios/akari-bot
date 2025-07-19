import re
from html import unescape

import orjson as json
from bs4 import BeautifulSoup

from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import Plain, Image, Url
from core.component import module
from core.i18n import Locale
from core.utils.http import get_url
from core.utils.image import msgchain2image
from modules.wiki.utils.screenshot_image import generate_screenshot_v2
from modules.wiki.utils.wikilib import WikiLib
from .teahouse import get_rss as get_teahouse_rss


async def get_weekly(with_img=False, zh_tw=False):
    locale = Locale("zh_cn" if not zh_tw else "zh_tw")
    result = json.loads(await get_url(
        "https://zh.minecraft.wiki/api.php?action=parse&page=Template:Mainpage_section_featured_article&prop=text|revid|images&format=json" +
        ("&variant=zh-tw" if zh_tw else ""),
        200))
    b_result = BeautifulSoup(result["parse"]["text"]["*"], "html.parser")
    html = b_result.find("div", class_="mp-section")
    el = html.find("div").find_all('div')
    content = el[1]
    text = re.sub(r"<p>", "\n", str(content))  # 分段
    text = re.sub(r"<(.*?)>", "", text, flags=re.DOTALL)  # 移除所有 HTML 标签
    text = re.sub(r"\n\n\n", "\n\n", text)  # 移除不必要的空行
    text = re.sub(r"\n*$", "", text)
    text = unescape(text)
    img = el[0].find("a")

    img_filename = re.match(r"/w/(.*)", img.attrs["href"]) if img else None
    page = re.findall(r"(?<=<b><a href=\").*?(?=\")", str(content))
    if (page and page[0] == "/w/%E7%8E%BB%E7%92%83"):
        msg_list = MessageChain.assign([Plain(locale.t("weekly.message.expired"))])
    else:
        msg_list = MessageChain.assign([Plain(locale.t("weekly.message.prompt", text=text))])
    imglink = None
    if img_filename:
        get_image = await (WikiLib("https://zh.minecraft.wiki/")).parse_page_info(img_filename.group(1))
        if get_image.status:
            imglink = get_image.file
    msg_list.append(
        Plain(
            locale.t(
                "weekly.message.link",
                img=imglink if imglink else locale.t("message.none"),
                article=str(
                    Url(f"https://zh.minecraft.wiki{page[0]}") if page else locale.t("message.none")),
                link=str(
                    Url(f"https://zh.minecraft.wiki/wiki/?oldid={str(result["parse"]["revid"])}")))))
    if imglink and with_img:
        msg_list.append(Image(path=imglink))

    return msg_list


async def get_weekly_img(with_img=False, zh_tw=False):
    # locale = Locale("zh_cn" if not zh_tw else "zh_tw")
    img = await generate_screenshot_v2("https://zh.minecraft.wiki/w/Template:Mainpage_section_featured_article" +
                                       ("?variant=zh-tw" if zh_tw else ""), content_mode=False, allow_special_page=True,
                                       element=["div.mp-section"])
    msg_ = []
    if img:
        for i in img:
            msg_.append(Image(i))
    if with_img:
        """result = json.loads(await get_url(
            "https://zh.minecraft.wiki/api.php?action=parse&page=Minecraft_Wiki/weekly&prop=images&format=json" +
            ("&variant=zh-tw" if zh_tw else ""),
            200))
        img = result["parse"]["images"]
        if img:
            get_image = await (WikiLib("https://zh.minecraft.wiki/wiki/")).parse_page_info("File:" + img[0])
            if get_image.status:
                msg_.append(Plain(locale.t("weekly.message.image", img=get_image.file)))"""
    return msg_


wky = module("weekly", developers=["Dianliang233"], support_languages=["zh_cn", "zh_tw"], doc=True)


@wky.command("{{I18N:weekly.help}}")
async def _(msg: Bot.MessageSession):
    weekly = await get_weekly(msg.session_info.client_name in ["QQ", "TEST"],
                              zh_tw=msg.session_info.locale.locale == "zh_tw")
    await msg.finish(weekly)


@wky.command("image {{I18N:weekly.help.image}}")
async def _(msg: Bot.MessageSession):
    await msg.finish(await get_weekly_img(msg.session_info.client_name in ["QQ", "TEST"],
                                          zh_tw=msg.session_info.locale.locale == "zh_tw"))


@wky.command("teahouse {{I18N:weekly.help.teahouse}}")
async def _(msg: Bot.MessageSession):
    weekly = await get_teahouse_rss()
    await msg.finish(weekly)


@wky.command("teahouse image {{I18N:weekly.help.teahouse}}")
async def _(msg: Bot.MessageSession):
    weekly = await get_teahouse_rss()
    imgchain = []
    for img in await msgchain2image(Plain(weekly), msg):
        imgchain.append(Image(img))
    await msg.finish(imgchain)
