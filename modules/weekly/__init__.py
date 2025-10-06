import re
from html import unescape
from typing import Awaitable, Callable, List, cast

import orjson as json
from bs4 import BeautifulSoup

from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import Plain, Image, Url
from core.builtins.types import MessageElement
from core.component import module
from core.i18n import Locale
from core.logger import Logger
from core.utils.http import get_url
from core.utils.image import msgchain2image
from modules.wiki.utils.screenshot_image import generate_screenshot_v2
from modules.wiki.utils.wikilib import WikiLib
from .rss_utils import RSSFeedError
from .teahouse import get_rss as get_teahouse_rss
from .ysarchives import get_rss as get_ysarchives_rss


async def _fetch_rss_with_fallback(
    fetcher: Callable[[], Awaitable[str]], feed_key: str, locale: Locale
) -> str:
    try:
        return await fetcher()
    except RSSFeedError as exc:
        Logger.warning(f"weekly.{feed_key}: {exc}")
    except Exception:
        Logger.exception(f"weekly.{feed_key}: unexpected error")
    return locale.t("weekly.message.rss_error", source=locale.t(f"weekly.feed.{feed_key}"))


async def _finish_text(msg: Bot.MessageSession, text: str):
    await msg.finish(MessageChain.assign([Plain(text)]))


async def _finish_text_as_image(msg: Bot.MessageSession, text: str):
    chain = MessageChain.assign([Plain(text)])
    images = await msgchain2image(chain, msg)
    if not images or isinstance(images, bool):
        await msg.finish(chain)
        return
    message_images = cast(List[MessageElement], list(images))
    await msg.finish(MessageChain.assign(message_images))


def _resolve_locale(msg: Bot.MessageSession) -> Locale:
    return msg.session_info.locale or Locale("zh_cn")


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
                    Url(f"https://zh.minecraft.wiki/wiki/?oldid={result['parse']['revid']}")
                ),
            )
        )
    )
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
    locale = _resolve_locale(msg)
    weekly = await get_weekly(
        msg.session_info.client_name in ["QQ", "TEST"],
        zh_tw=locale.locale == "zh_tw",
    )
    await msg.finish(weekly)


@wky.command("image {{I18N:weekly.help.image}}")
async def _(msg: Bot.MessageSession):
    locale = _resolve_locale(msg)
    await msg.finish(
        await get_weekly_img(
            msg.session_info.client_name in ["QQ", "TEST"],
            zh_tw=locale.locale == "zh_tw",
        )
    )


@wky.command("teahouse {{I18N:weekly.help.teahouse}}")
async def _(msg: Bot.MessageSession):
    locale = _resolve_locale(msg)
    weekly = await _fetch_rss_with_fallback(get_teahouse_rss, "teahouse", locale)
    await _finish_text(msg, weekly)


@wky.command("teahouse image {{I18N:weekly.help.teahouse}}")
async def _(msg: Bot.MessageSession):
    locale = _resolve_locale(msg)
    weekly = await _fetch_rss_with_fallback(get_teahouse_rss, "teahouse", locale)
    await _finish_text_as_image(msg, weekly)


@wky.command("ysarchives {{I18N:weekly.help.ysarchives}}")
async def _(msg: Bot.MessageSession):
    locale = _resolve_locale(msg)
    weekly = await _fetch_rss_with_fallback(get_ysarchives_rss, "ysarchives", locale)
    await _finish_text(msg, weekly)


@wky.command("ysarchives image {{I18N:weekly.help.ysarchives}}")
async def _(msg: Bot.MessageSession):
    locale = _resolve_locale(msg)
    weekly = await _fetch_rss_with_fallback(get_ysarchives_rss, "ysarchives", locale)
    await _finish_text_as_image(msg, weekly)
