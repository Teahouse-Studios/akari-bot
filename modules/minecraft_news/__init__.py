import asyncio
import json
import traceback
import aiohttp
import random

from config import Config
from database import BotDBUtil
from core.utils import get_url, download_to_cache
from core.scheduler import Scheduler
from core.loader.decorator import command
from core.elements import FetchTarget, Plain, Image
from core.logger import Logger


@command('minecraft_news', autorun=True)
async def start_check_news(bot: FetchTarget):
    baseurl = 'https://www.minecraft.net'
    url = 'https://www.minecraft.net/content/minecraft-net/_jcr_content.articles.grid?tileselection=auto&tagsPath=minecraft:article/news,minecraft:article/insider,minecraft:article/culture,minecraft:article/merch,minecraft:stockholm/news,minecraft:stockholm/guides,minecraft:stockholm/deep-dives,minecraft:stockholm/merch,minecraft:stockholm/events,minecraft:stockholm/minecraft-builds,minecraft:stockholm/marketplace&offset=0&pageSize=10'
    webrender = Config('infobox_render')
    get = webrender + 'source?url=' + url
    if not webrender:
        return
    getpage = await get_url(get)
    title_list = []
    if getpage:
        o_nws = json.loads(getpage)['article_grid']
        for o_article in o_nws:
            o_default_tile = o_article['default_tile']['title']
            title_list.append(o_default_tile)
    Logger.info(str(title_list))
    @Scheduler.scheduled_job('interval', seconds=600)
    async def check_news():
        user_list = []
        get_all_enabled_user = BotDBUtil.Module.get_enabled_this('minecraft_news')
        for x in get_all_enabled_user:
            fetch = await bot.fetch_target(x)
            if fetch:
                user_list.append(fetch)
        if not user_list:
            return
        Logger.info('Checking Minecraft news...' + str(title_list))
        async with aiohttp.ClientSession() as session:
            async with session.get(get) as resp:
                status = resp.status
                if status == 200:
                    nws = json.loads(await resp.read())['article_grid']
                    for article in nws:
                        default_tile = article['default_tile']
                        title = default_tile['title']
                        image = baseurl + default_tile['image']['imageURL']
                        desc = default_tile['sub_header']
                        link = baseurl + article['article_url']
                        if title not in title_list:
                            title_list.append(title)
                            articletext = f'Minecraft官网发布了新的文章：\n{title}\n{link}\n{desc}\n'
                            image = await download_to_cache(webrender + 'source?url=' + baseurl + image)
                            for x in user_list:
                                await x.sendMessage(articletext)
                                try:
                                    if image:
                                        await x.sendMessage([Image(image)])
                                except Exception:
                                    traceback.print_exc()
                    Logger.info('Minecraft news checked.')
                else:
                    Logger.info('Check minecraft news failed:' + str(status))
