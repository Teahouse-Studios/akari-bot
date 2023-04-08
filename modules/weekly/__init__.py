import re

import ujson as json

from core.builtins import Bot
from core.builtins import Plain, Image, Url
from core.component import module
from core.utils.http import get_url
from core.utils.i18n import Locale
from .teahouse import get_rss as get_teahouse_rss
from core.utils.image import msgchain2image


async def get_weekly(with_img=False, zh_tw=False):
    locale = Locale('zh_cn' if not zh_tw else 'zh_tw')
    result = json.loads(await get_url(
        'https://minecraft.fandom.com/zh/api.php?action=parse&page=Minecraft_Wiki/weekly&prop=text|revid&format=json' +
        ('&variant=zh-tw' if zh_tw else ''),
        200))
    html = result['parse']['text']['*']
    text = re.sub(r'<p>', '\n', html)  # 分段
    text = re.sub(r'<(.*?)>', '', text, flags=re.DOTALL)  # 移除所有 HTML 标签
    text = re.sub(r'\n\n\n', '\n\n', text)  # 移除不必要的空行
    text = re.sub(r'\n*$', '', text)
    img = re.findall(r'(?<=src=")(.*?)(?=/revision/latest/scale-to-(width|height)-down/\d{3}\?cb=\d{14}?")', html)
    page = re.findall(r'(?<=<b><a href=").*?(?=")', html)
    msg_list = [Plain(locale.t("weekly.message.expired") if page[
                                                                    0] == '/zh/wiki/%E7%8E%BB%E7%92%83' else locale.t(
        "weekly.message", text=text))]
    if img:
        msg_list.append(Plain(locale.t("weekly.message.link", img=str(Url(f'{img[0][0]}?format=original')),
                                           article=str(Url(f'https://minecraft.fandom.com{page[0]}')),
                                           link=str(
                                               Url(f'https://minecraft.fandom.com/zh/wiki/?oldid={str(result["parse"]["revid"])}')))))
        if with_img:
            msg_list.append(Image(path=img[0][0]))

    return msg_list


wky = module('weekly', developers=['Dianliang233'], support_languages=['zh_cn', 'zh_tw'])


@wky.handle('{{weekly.help}}')
async def _(msg: Bot.MessageSession):
    weekly = await get_weekly(True if msg.target.clientName in ['QQ', 'TEST'] else False,
                              zh_tw=True if msg.locale.locale == 'zh_tw' else False)
    await msg.finish(weekly)


@wky.handle('image {{weekly.image.help}}')
async def _(msg: Bot.MessageSession):
    weekly = await get_weekly(True if msg.target.clientName in ['QQ', 'TEST'] else False,
                              zh_tw=True if msg.locale.locale == 'zh_tw' else False)
    await msg.finish(Image(await msgchain2image(weekly)))


@wky.handle('teahouse {{weekly.teahouse.help}}')
async def _(msg: Bot.MessageSession):
    weekly = await get_teahouse_rss()
    await msg.finish(weekly)
