import os
import random
import traceback
from datetime import datetime, timedelta
from urllib.parse import quote

import ujson as json

from config import Config
from core.component import on_schedule
from core.elements import FetchTarget, IntervalTrigger, PrivateAssets, Url
from core.logger import Logger
from core.utils import get_url, get_stored_list, update_stored_list


class Article:
    count = 10
    tags = ['minecraft:article/news', 'minecraft:article/insider', 'minecraft:article/culture',
            'minecraft:article/merch', 'minecraft:stockholm/news', 'minecraft:stockholm/guides',
            'minecraft:stockholm/deep-dives', 'minecraft:stockholm/merch', 'minecraft:stockholm/events',
            'minecraft:stockholm/minecraft-builds', 'minecraft:stockholm/marketplace']

    @staticmethod
    def random_tags():
        tags = Article.tags
        long = len(tags)
        m = long // 2
        random_tags = []

        def random_choice():
            c = random.choice(tags)
            if c not in random_tags:
                random_tags.append(c)
            else:
                random_choice()

        for _ in range(m):
            random_choice()
        return random_tags


@on_schedule('minecraft_news', developers=['_LittleC_', 'OasisAkari', 'Dianliang233'],
             recommend_modules=['feedback_news'], trigger=IntervalTrigger(seconds=60 if not Config('slower_schedule') else 180),
             desc='开启后将会自动推送来自Minecraft官网的新闻。', alias='minecraftnews')
async def start_check_news(bot: FetchTarget):
    baseurl = 'https://www.minecraft.net'
    url = quote(
        f'https://www.minecraft.net/content/minecraft-net/_jcr_content.articles.grid?tileselection=auto&tagsPath={",".join(Article.random_tags())}&offset=0&pageSize={Article.count}')
    webrender = Config('web_render')
    if not webrender:
        return
    get = webrender + 'source?url=' + url
    getpage = await get_url(get)
    if getpage:
        alist = get_stored_list(bot, 'mcnews')
        o_json = json.loads(getpage)
        o_nws = o_json['article_grid']
        Article.count = o_json['article_count']
        for o_article in o_nws:
            default_tile = o_article['default_tile']
            title = default_tile['title']
            desc = default_tile['sub_header']
            link = baseurl + o_article['article_url']
            articletext = f'Minecraft官网发布了新的文章：\n{title}\n  {desc}\n{str(Url(link))}'
            if title not in alist:
                publish_date = datetime.strptime(o_article['publish_date'], '%d %B %Y %H:%M:%S %Z')
                now = datetime.now()
                if now - publish_date < timedelta(days=2):
                    await bot.post_message('minecraft_news', articletext)
                alist.append(title)
                update_stored_list(bot, 'mcnews', alist)


@on_schedule('feedback_news', developers=['Dianliang233'], recommend_modules=['minecraft_news'],
             trigger=IntervalTrigger(seconds=300), desc='开启后将会推送来自Minecraft Feedback的更新记录。',
             alias='feedbacknews')
async def feedback_news(bot: FetchTarget):
    sections = [{'name': 'beta',
                 'url': 'https://minecraftfeedback.zendesk.com/api/v2/help_center/en-us/sections/360001185332/articles?per_page=5'},
                {'name': 'article',
                 'url': 'https://minecraftfeedback.zendesk.com/api/v2/help_center/en-us/sections/360001186971/articles?per_page=5'}]
    for section in sections:
        try:
            alist = get_stored_list(bot, 'mcfeedbacknews')
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
                    await bot.post_message('feedback_news',
                                           f'Minecraft Feedback 发布了新的文章：\n{name}\n{str(Url(link))}')
                    alist.append(name)
                    update_stored_list(bot, 'mcfeedbacknews', alist)
        except Exception:
            traceback.print_exc()
