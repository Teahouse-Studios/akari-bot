import json
import re

from core.elements import Plain, Image, MessageSession
from core.loader.decorator import command
from core.utils import get_url

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
    sended_img = Image(path=img[0][0]) if img else Plain('\n（发生错误：图片获取失败）')
    msg = '发生错误：本周页面已过期，请联系中文 Minecraft Wiki 更新。' if page[
                                                            0] == '/zh/wiki/%E7%8E%BB%E7%92%83' else '本周的每周页面：\n\n' + text + '\n图片：' + \
                                                                                                    img[0][
                                                                                                        0] + '?format=original\n\n页面链接：https://minecraft.fandom.com' + \
                                                                                                    page[
                                                                                                        0] + '\n每周页面：https://minecraft.fandom.com/zh/wiki/?oldid=' + str(
        result['parse']['revid'])

    return msg, sended_img

@command('weekly', help_doc=('~weekly {获取中文 Minecraft Wiki 的每周页面}'))
async def weekly(msg: MessageSession):
    weekly = await get_weekly()
    await msg.sendMessage(weekly[0], weekly[1])
