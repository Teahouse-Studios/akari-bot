import re
from html import unescape
from bs4 import BeautifulSoup

import ujson as json

from core.builtins import Bot, Plain, Image, Url
from core.component import module
from core.utils.http import get_url
from core.utils.i18n import Locale
from core.utils.image import msgchain2image
from modules.wiki.utils.screenshot_image import generate_screenshot_v2
from modules.wiki.utils.wikilib import WikiLib
from .teahouse import get_rss as get_teahouse_rss


async def get_weekly(with_img=False, zh_tw=False):
    locale = Locale('zh_cn' if not zh_tw else 'zh_tw')
    result = json.loads(await get_url(
        'https://zh.minecraft.wiki/api.php?action=parse&page=Minecraft_Wiki&prop=text|revid|images&format=json' +
        ('&variant=zh-tw' if zh_tw else ''),
        200))
    b_result = BeautifulSoup(result['parse']['text']['*'], 'html.parser')
    html = b_result.find('div', id='fp-section-weekly')

    content = html.find('div', class_='weekly-content')
    text = re.sub(r'<p>', '\n', str(content))  # 分段
    text = re.sub(r'<(.*?)>', '', text, flags=re.DOTALL)  # 移除所有 HTML 标签
    text = re.sub(r'\n\n\n', '\n\n', text)  # 移除不必要的空行
    text = re.sub(r'\n*$', '', text)
    text = unescape(text)
    img = html.find('div', class_='weekly-image').find(class_='image')

    img_filename = re.match(r'/w/(.*)', img.attrs['href'])
    page = re.findall(r'(?<=<b><a href=").*?(?=")', str(content))
    msg_list = [Plain(locale.t("weekly.message.expired") if page[
        0] == '/w/%E7%8E%BB%E7%92%83' else locale.t(
        "weekly.message", text=text))]
    imglink = None
    if img_filename:
        get_image = await (WikiLib('https://zh.minecraft.wiki/')).parse_page_info(img_filename.group(1))
        if get_image.status:
            imglink = get_image.file
    msg_list.append(
        Plain(
            locale.t(
                "weekly.message.link",
                img=imglink if imglink else locale.t("none"),
                article=str(
                    Url(f'https://zh.minecraft.wiki{page[0]}')),
                link=str(
                    Url(f'https://zh.minecraft.wiki/wiki/?oldid={str(result["parse"]["revid"])}')))))
    if imglink and with_img:
        msg_list.append(Image(path=imglink))

    return msg_list


async def get_weekly_img(with_img=False, zh_tw=False):
    locale = Locale('zh_cn' if not zh_tw else 'zh_tw')
    img = await generate_screenshot_v2('https://zh.minecraft.wiki/wiki/Minecraft_Wiki/' +
                                       ('?variant=zh-tw' if zh_tw else ''), content_mode=False, allow_special_page=True,
                                       element=['div#fp-section-weekly'])
    msg_ = []
    if img:
        msg_.append(Image(path=img))
    if with_img:
        """result = json.loads(await get_url(
            'https://zh.minecraft.wiki/api.php?action=parse&page=Minecraft_Wiki/weekly&prop=images&format=json' +
            ('&variant=zh-tw' if zh_tw else ''),
            200))
        img = result['parse']['images']
        if img:
            get_image = await (WikiLib('https://zh.minecraft.wiki/wiki/')).parse_page_info('File:' + img[0])
            if get_image.status:
                msg_.append(Plain(locale.t("weekly.message.image", img=get_image.file)))"""
    return msg_


wky = module('weekly', developers=['Dianliang233'], support_languages=['zh_cn', 'zh_tw'])


@wky.handle('{{weekly.help}}')
async def _(msg: Bot.MessageSession):
    weekly = await get_weekly(True if msg.target.client_name in ['QQ', 'TEST'] else False,
                              zh_tw=True if msg.locale.locale == 'zh_tw' else False)
    await msg.finish(weekly)


@wky.handle('image {{weekly.help.image}}')
async def _(msg: Bot.MessageSession):
    await msg.finish(await get_weekly_img(True if msg.target.client_name in ['QQ', 'TEST'] else False,
                                          zh_tw=True if msg.locale.locale == 'zh_tw' else False))


@wky.handle('teahouse {{weekly.help.teahouse}}')
async def _(msg: Bot.MessageSession):
    weekly = await get_teahouse_rss()
    await msg.finish(weekly)


@wky.handle('teahouse image {{weekly.help.teahouse}}')
async def _(msg: Bot.MessageSession):
    weekly = await get_teahouse_rss()
    await msg.finish(Image(await msgchain2image([Plain(weekly)], msg)))
