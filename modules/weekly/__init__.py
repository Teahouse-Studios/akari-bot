import re

import ujson as json

from core.component import on_command
from core.elements import Plain, Image, MessageSession, Url
from core.utils import get_url
from .teahouse import get_rss as get_teahouse_rss


async def get_weekly():
    result = json.loads(await get_url(
        'https://minecraft.fandom.com/zh/api.php?action=parse&page=Minecraft_Wiki/weekly&prop=text|revid&format=json'))
    html = result['parse']['text']['*']
    text = re.sub(r'<p>', '\n', html)  # 分段
    text = re.sub(r'<(.*?)>', '', text, flags=re.DOTALL)  # 移除所有 HTML 标签
    text = re.sub(r'\n\n\n', '\n\n', text)  # 移除不必要的空行
    text = re.sub(r'\n*$', '', text)
    img = re.findall(r'(?<=src=")(.*?)(?=/revision/latest/scale-to-(width|height)-down/\d{3}\?cb=\d{14}?")', html)
    page = re.findall(r'(?<=<b><a href=").*?(?=")', html)
    msg_list = [Plain('发生错误：本周页面已过期，请联系中文 Minecraft Wiki 更新。' if page[
                                                                     0] == '/zh/wiki/%E7%8E%BB%E7%92%83' else '本周的每周页面：\n\n' + text)]
    if img:
        msg_list.append(Plain(f'图片：' + str(Url(f'{img[0][0]}?format=original')) +
                              f'\n\n页面链接：' + str(Url(f'https://minecraft.fandom.com{page[0]}')) +
                              f'\n每周页面：' + str(
            Url(f'https://minecraft.fandom.com/zh/wiki/?oldid={str(result["parse"]["revid"])}'))))
        msg_list.append(Image(path=img[0][0]))

    return msg_list


wky = on_command('weekly', developers=['Dianliang233'], desc='获取中文 Minecraft Wiki 的每周页面')


@wky.handle()
async def _(msg: MessageSession):
    weekly = await get_weekly()
    await msg.sendMessage(weekly)


@wky.handle('teahouse {获取茶馆周报}')
async def _(msg: MessageSession):
    weekly = await get_teahouse_rss()
    await msg.sendMessage(weekly)
