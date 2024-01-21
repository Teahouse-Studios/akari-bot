import random
import traceback
from datetime import datetime, timedelta
from urllib.parse import quote

import ujson as json

from config import Config, CFG
from core.builtins import Url, I18NContext
from core.logger import Logger
from core.queue import JobQueue
from core.scheduler import Scheduler, IntervalTrigger
from core.utils.http import get_url
from core.utils.storedata import get_stored_list, update_stored_list

web_render = CFG.get_url('web_render')
web_render_local = CFG.get_url('web_render_local')


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


@Scheduler.scheduled_job(IntervalTrigger(seconds=60 if not Config('slower_schedule') else 180))
async def start_check_news(use_local=True):
    baseurl = 'https://www.minecraft.net'
    url = quote(
        f'https://www.minecraft.net/content/minecraft-net/_jcr_content.articles.grid?tileselection=auto&tagsPath={",".join(Article.random_tags())}&offset=0&pageSize={Article.count}')
    if not web_render_local:
        if not web_render:
            Logger.warn('[Webrender] Webrender is not configured.')
            return
        use_local = False
    try:
        get = (web_render_local if use_local else web_render) + 'source?url=' + url
        getpage = await get_url(get, 200, attempt=1, logging_err_resp=False)
        if getpage:
            alist = get_stored_list('scheduler', 'mcnews')
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
                        await JobQueue.trigger_hook_all('minecraft_news', message=[I18NContext('minecraft_news.message.minecraft_news',
                                                                                               title=title, desc=desc, link=link).to_dict()])
                    alist.append(title)
                    update_stored_list('scheduler', 'mcnews', alist)
    except Exception:
        if Config('debug'):
            Logger.error(traceback.format_exc())


@Scheduler.scheduled_job(IntervalTrigger(seconds=300))
async def feedback_news():
    sections = [{'name': 'beta',
                 'url': 'https://minecraftfeedback.zendesk.com/api/v2/help_center/en-us/sections/360001185332/articles?per_page=5'},
                {'name': 'article',
                 'url': 'https://minecraftfeedback.zendesk.com/api/v2/help_center/en-us/sections/360001186971/articles?per_page=5'}]
    for section in sections:
        try:
            alist = get_stored_list('scheduler', 'mcfeedbacknews')
            get = await get_url(section['url'], 200, attempt=1, logging_err_resp=False)
            res = json.loads(get)
            articles = []
            for i in res['articles']:
                articles.append(i)
            for article in articles:
                if article['name'] not in alist:
                    name = article['name']
                    link = article['html_url']
                    Logger.info(f'Huh, we find {name}.')
                    await JobQueue.trigger_hook_all('feedback_news',
                                                    message=[I18NContext('minecraft_news.message.feedback_news',
                                                                         name=name, link=str(Url(link))).to_dict()])
                    alist.append(name)
                    update_stored_list('scheduler', 'mcfeedbacknews', alist)
        except Exception:
            if Config('debug'):
                Logger.error(traceback.format_exc())
