import ujson as json
import os
import traceback
from datetime import datetime, timedelta
from urllib.parse import quote

import ujson as json

from config import Config
from core.component import on_schedule
from core.elements import FetchTarget, IntervalTrigger, PrivateAssets
from core.logger import Logger
from core.utils import get_url


def getfileversions(path):
    if not os.path.exists(path):
        a = open(path, 'a', encoding='utf-8')
        a.close()
    w = open(path, 'r+', encoding='utf-8')
    s = w.read().split('\n')
    w.close()
    return s


class Article:
    count = 10


@on_schedule('minecraft_news', developers=['_LittleC_', 'OasisAkari', 'Dianliang233'],
             recommend_modules=['feedback_news'], trigger=IntervalTrigger(seconds=300), desc='开启后将会推送来自Minecraft官网的新闻。')
async def start_check_news(bot: FetchTarget):
    Logger.info('Checking Minecraft news...')
    file_ = os.path.abspath(f'{PrivateAssets.path}/mcnews.txt')
    baseurl = 'https://www.minecraft.net'
    url = quote(
        f'https://www.minecraft.net/content/minecraft-net/_jcr_content.articles.grid?tileselection=auto&tagsPath=minecraft:article/news,minecraft:article/insider,minecraft:article/culture,minecraft:article/merch,minecraft:stockholm/news,minecraft:stockholm/guides,minecraft:stockholm/deep-dives,minecraft:stockholm/merch,minecraft:stockholm/events,minecraft:stockholm/minecraft-builds,minecraft:stockholm/marketplace&offset=0&pageSize={Article.count}')
    webrender = Config('web_render')
    get = webrender + 'source?url=' + url
    if not webrender:
        return
    getpage = await get_url(get)
    if getpage:
        alist = getfileversions(file_)
        o_json = json.loads(getpage)
        o_nws = o_json['article_grid']
        Article.count = o_json['article_count']
        for o_article in o_nws:
            default_tile = o_article['default_tile']
            title = default_tile['title']
            desc = default_tile['sub_header']
            link = baseurl + o_article['article_url']
            articletext = f'Minecraft官网发布了新的文章：\n{title}\n{link}\n{desc}'
            if title not in alist:
                publish_date = datetime.strptime(o_article['publish_date'], '%d %B %Y %H:%M:%S %Z')
                now = datetime.now()
                if now - publish_date < timedelta(days=2):
                    await bot.post_message('minecraft_news', articletext)
                addversion = open(file_, 'a', encoding='utf-8')
                addversion.write('\n' + title)
                addversion.close()
    Logger.info('Minecraft news checked.')


@on_schedule('feedback_news', developers=['Dianliang233'], recommend_modules=['minecraft_news'],
             trigger=IntervalTrigger(seconds=300), desc='开启后将会推送来自Minecraft Feedback的更新记录。')
async def feedback_news(bot: FetchTarget):
    sections = [{'name': 'beta',
                 'url': 'https://minecraftfeedback.zendesk.com/api/v2/help_center/en-us/sections/360001185332/articles?per_page=5'},
                {'name': 'article',
                 'url': 'https://minecraftfeedback.zendesk.com/api/v2/help_center/en-us/sections/360001186971/articles?per_page=5'}]
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
                    addversion = open(version_file, 'a', encoding='utf-8')
                    addversion.write('\n' + name)
                    addversion.close()
        except Exception:
            traceback.print_exc()
            print(get)
