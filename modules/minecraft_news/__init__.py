import asyncio
import traceback

from graia.application import MessageChain
from graia.application.message.elements.internal import Plain, Image
from graia.scheduler import GraiaScheduler
from graia.scheduler.timers import every_minute

from core.broadcast import bcc
from core.template import logger_info
import json
import aiohttp
from database import BotDB
from .database import MD as db
from datetime import datetime


database = db()
check_enable_modules_all = BotDB.check_enable_modules_all


scheduler = GraiaScheduler(bcc.loop, bcc)

async def start_check_news(app):
    @scheduler.schedule(every_minute())
    async def check_news():
        logger_info('Checking Minecraft news...')
        baseurl = 'https://www.minecraft.net'
        url = 'https://www.minecraft.net/content/minecraft-net/_jcr_content.articles.grid?tileselection=auto&tagsPath=minecraft:article/news,minecraft:article/insider,minecraft:article/culture,minecraft:article/merch,minecraft:stockholm/news,minecraft:stockholm/guides,minecraft:stockholm/deep-dives,minecraft:stockholm/merch,minecraft:stockholm/events,minecraft:stockholm/minecraft-builds,minecraft:stockholm/marketplace&propResPath=/content/minecraft-net/language-masters/zh-hans/jcr:content/root/generic-container/par/bleeding_page_sectio_1278766118/page-section-par/grid&offset=0&count=500&pageSize=10'
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                status = resp.status
                if status == 200:
                    nws = json.loads(await resp.read())['article_grid']
                    for article in nws:
                        default_tile = article['default_tile']
                        title = default_tile['title']
                        image = baseurl + default_tile['image']['imageURL']
                        desc = default_tile['sub_header']
                        link = baseurl + article['article_url']
                        date = article['publish_date']
                        q = database.check_exist(title)
                        if not q:
                            database.add_news(title, link, desc, image, date)
                            articletext = f'Minecraft官网发布了新的文章：\n{title}\n{link}\n{desc}'
                            msgchain = MessageChain.create([Plain(articletext), Image.fromNetworkAddress(image)])
                            for qqgroup in check_enable_modules_all('group_permission', 'minecraft_news'):
                                try:
                                    await app.sendGroupMessage(int(qqgroup), msgchain)
                                    await asyncio.sleep(0.5)
                                except Exception:
                                    traceback.print_exc()
                            for qqfriend in check_enable_modules_all('friend_permission', 'minecraft_news'):
                                try:
                                    await app.sendFriendMessage(int(qqfriend), msgchain)
                                    await asyncio.sleep(0.5)
                                except Exception:
                                    traceback.print_exc()
                            logger_info(articletext)
                    logger_info('Minecraft news checked.')


                else:
                    logger_info('Check minecraft news failed:' + status)


rss = {'minecraft_news': start_check_news}
options = ['minecraft_news']
friend_options = options