import random
import traceback
from datetime import datetime, timedelta
from urllib.parse import quote

import ujson as json

from config import Config
from core.builtins import Url, Bot
from core.component import module
from core.logger import Logger
from core.scheduler import IntervalTrigger
from core.utils.http import get_url
from core.utils.storedata import get_stored_list, update_stored_list


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


bot = Bot.FetchTarget

minecraft_news = module('minecraft_news', developers=['_LittleC_', 'OasisAkari', 'Dianliang233'],
                        recommend_modules=['feedback_news'],
                        desc='{minecraft_news.help.minecraft_news}', alias='minecraftnews')


@minecraft_news.handle(IntervalTrigger(seconds=60 if not Config('slower_schedule') else 180))
async def start_check_news():
    baseurl = 'https://www.minecraft.net'
    url = quote(
        f'https://www.minecraft.net/content/minecraft-net/_jcr_content.articles.grid?tileselection=auto&tagsPath={",".join(Article.random_tags())}&offset=0&pageSize={Article.count}')
    webrender = Config('web_render')
    if not webrender:
        return
    try:
        get = webrender + '/source?url=' + url
        getpage = await get_url(get, 200, attempt=1, logging_err_resp=False)
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
                if title not in alist:
                    publish_date = datetime.strptime(o_article['publish_date'], '%d %B %Y %H:%M:%S %Z')
                    now = datetime.now()
                    if now - publish_date < timedelta(days=2):
                        await bot.post_message('minecraft_news', 'minecraft_news.message.minecraft_news', i18n=True,
                                               title=title, desc=desc, link=str(Url(link)))
                    alist.append(title)
                    update_stored_list(bot, 'mcnews', alist)
    except Exception:
        if Config('debug'):
            Logger.error(traceback.format_exc())


feedback_news = module('feedback_news', developers=['Dianliang233'], recommend_modules=['minecraft_news'],
                       desc='{minecraft_news.help.feedback_news}',
                       alias='feedbacknews')


@feedback_news.handle(IntervalTrigger(seconds=300))
async def feedback_news():
    sections = [{'name': 'beta',
                 'url': 'https://minecraftfeedback.zendesk.com/api/v2/help_center/en-us/sections/360001185332/articles?per_page=5'},
                {'name': 'article',
                 'url': 'https://minecraftfeedback.zendesk.com/api/v2/help_center/en-us/sections/360001186971/articles?per_page=5'}]
    for section in sections:
        try:
            alist = get_stored_list(bot, 'mcfeedbacknews')
            get = await get_url(section['url'], 200, attempt=1, logging_err_resp=False)
            res = json.loads(get)
            articles = []
            for i in res['articles']:
                articles.append(i)
            for article in articles:
                if article['name'] not in alist:
                    name = article['name']
                    link = article['html_url']
                    Logger.info(f'huh, we find {name}.')
                    await bot.post_message('feedback_news', 'minecraft_news.message.feedback_news', i18n=True,
                                           name=name, link=str(Url(link)))
                    alist.append(name)
                    update_stored_list(bot, 'mcfeedbacknews', alist)
        except Exception:
            if Config('debug'):
                Logger.error(traceback.format_exc())
