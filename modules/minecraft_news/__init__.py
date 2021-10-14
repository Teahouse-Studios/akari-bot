import aiohttp
import ujson as json
import traceback
import os

from config import Config
from core.elements import FetchTarget, IntervalTrigger
from core.decorator import command, schedule
from core.logger import Logger
from core.scheduler import Scheduler
from core.utils import get_url, PrivateAssets
from database import BotDBUtil


@command('minecraft_news', developers=['_LittleC_', 'OasisAkari', 'Dianliang233'], recommend_modules=['feedback_news'], autorun=True)
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
        get_all_enabled_user = BotDBUtil.Module.get_enabled_this('minecraft_news')
        user_list = await bot.fetch_target_list(get_all_enabled_user)
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
                        desc = default_tile['sub_header']
                        link = baseurl + article['article_url']
                        if title not in title_list:
                            title_list.append(title)
                            articletext = f'Minecraft官网发布了新的文章：\n{title}\n{link}\n{desc}'
                            await bot.post_message('minecraft_news', articletext, user_list=user_list)
                    Logger.info('Minecraft news checked.')
                else:
                    Logger.info('Check minecraft news failed:' + str(status))


def getfileversions(path):
    if not os.path.exists(path):
        a = open(path, 'a')
        a.close()
    w = open(path, 'r+')
    s = w.read().split('\n')
    w.close()
    return s


@schedule('feedback_news', developers=['Dianliang233'], recommend_modules=['minecraft_news'], trigger=IntervalTrigger(seconds=300))
async def feedback_news(bot: FetchTarget):
    sections = [{'name': 'beta', 'url': 'https://minecraftfeedback.zendesk.com/api/v2/help_center/en-us/sections/360001185332/articles?per_page=5'},
                {'name': 'article', 'url': 'https://minecraftfeedback.zendesk.com/api/v2/help_center/en-us/sections/360001186971/articles?per_page=5'}]
    for section in sections:
        try:
            name = section['name']
            version_file = os.path.abspath(f'{PrivateAssets.path}/feedback_{name}.txt')
            alist = getfileversions(version_file)
            get = await get_url(section['url'])
            res = json.loads(get)
            articles = []
            for i in res['articles']:
                articles.append(i)
            for article in articles:
                if article['name'] not in alist:
                    name = article['name']
                    link = article['html_url']
                    Logger.info(f'huh, we find {name}.')
                    alist.append(name)
                    await bot.post_message('feedback_news',
                                                    f'Minecraft Feedback 发布了新的文章：\n{name}\n{link}')
                    addversion = open(version_file, 'a')
                    addversion.write('\n' + name)
                    addversion.close()
        except Exception:
            traceback.print_exc()
            print(get)