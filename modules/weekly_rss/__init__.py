import asyncio
import json
import traceback
import re

from graia.application import MessageChain
from graia.application.message.elements.internal import Plain, Image
from graia.scheduler import GraiaScheduler
from graia.scheduler.timers import crontabify
from core.broadcast import bcc
from core.template import logger_info
from core.utils import get_url
from database import BotDB

check_enable_modules_all = BotDB.check_enable_modules_all
scheduler = GraiaScheduler(bcc.loop, bcc)


async def start_check_weekly(app):
    @scheduler.schedule(crontabify('30 8 * * MON'))
    async def check_weekly():
        logger_info('Checking MCWZH weekly...')
        result = json.loads(await get_url(
            'https://minecraft.fandom.com/zh/api.php?action=parse&page=Minecraft_Wiki/weekly&prop=text|revid&format=json'))
        html = result['parse']['text']['*']
        text = re.sub(r'<p>', '\n', html)  # 分段
        text = re.sub(r'<(.*?)>', '', text, flags=re.DOTALL)  # 移除所有 HTML 标签
        text = re.sub(r'\n\n\n', '\n\n', text)  # 移除不必要的空行
        text = re.sub(r'\n*$', '', text)
        img = re.findall(r'(?<=src=")(.*?)(?=/revision/latest/scale-to-(width|height)-down/\d{3}\?cb=\d{14}?")', html)
        page = re.findall(r'(?<=<b><a href=").*?(?=")', html)
        sended_img = Image.fromNetworkAddress(img[0][0]) if img else Plain('\n（发生错误：图片获取失败）')
        msg = '发生错误：本周页面已过期，请联系中文 Minecraft Wiki 更新。' if page[0] == '/zh/wiki/%E7%8E%BB%E7%92%83' else '本周的每周页面：\n\n' + text + '\n图片：' + \
                                                                                                      img[0][
                                                                                                          0] + '?format=original\n\n页面链接：https://minecraft.fandom.com' + \
                                                                                                      page[
                                                                                                          0] + '\n每周页面：https://minecraft.fandom.com/zh/wiki/?oldid=' + str(
        result['parse']['revid'])
        chain = MessageChain.create([Plain(msg), sended_img])
        for qqgroup in check_enable_modules_all('group_permission', 'weekly_rss'):
            try:
                await app.sendGroupMessage(int(qqgroup), chain)
                await asyncio.sleep(0.5)
            except Exception:
                traceback.print_exc()

        for qqfriend in check_enable_modules_all('friend_permission', 'weekly_rss'):
            try:
                await app.sendFriendMessage(int(qqfriend), chain)
                await asyncio.sleep(0.5)
            except Exception:
                traceback.print_exc()

        logger_info(msg)
        logger_info('Minecraft news checked.')


rss = {'weekly_rss': start_check_weekly}
options = ['weekly_rss']
friend_options = options
help = {'weekly_rss': {'help': '订阅中文 Minecraft Wiki 的每周页面（每周一 8：30 更新）。'}}
