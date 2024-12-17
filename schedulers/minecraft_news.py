import traceback
from urllib.parse import quote

import orjson as json

from core.builtins import Url, I18NContext, MessageChain
from core.config import Config
from core.logger import Logger
from core.queue import JobQueue
from core.scheduler import Scheduler, IntervalTrigger
from core.utils.http import get_url
from core.utils.storedata import get_stored_list, update_stored_list
from core.utils.web_render import webrender

"""class Article:
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
        return random_tags"""


@Scheduler.scheduled_job(
    IntervalTrigger(seconds=60 if not Config("slower_schedule", False) else 180)
)
async def start_check_news():
    baseurl = "https://www.minecraft.net"
    url = "https://www.minecraft.net/content/minecraftnet/language-masters/en-us/articles/jcr:content/root/container/image_grid_a.articles.json"
    try:
        get_webrender = webrender("source", quote(url))
        if get_webrender == url:
            Logger.debug("WebRender is not working, skip check minecraft news.")
            return
        getpage = await get_url(
            get_webrender,
            200,
            attempt=1,
            request_private_ip=True,
            logging_err_resp=False,
        )
        if getpage:
            alist = get_stored_list("scheduler", "mcnews")
            o_json = json.loads(getpage)
            o_nws = o_json["article_grid"]
            for o_article in o_nws:
                default_tile = o_article["default_tile"]
                title = default_tile["title"]
                desc = default_tile["sub_header"]
                link = baseurl + o_article["article_url"]
                if title not in alist:
                    await JobQueue.trigger_hook_all(
                        "minecraft_news",
                        message=MessageChain(
                            [
                                I18NContext(
                                    "minecraft_news.message.minecraft_news",
                                    title=title,
                                    desc=desc,
                                    link=link,
                                )
                            ]
                        ),
                    )
                    alist.append(title)
                    update_stored_list("scheduler", "mcnews", alist)
    except Exception:
        if Config("debug", False):
            Logger.error(traceback.format_exc())


@Scheduler.scheduled_job(IntervalTrigger(seconds=300))
async def feedback_news():
    sections = [
        {
            "name": "beta",
            "url": "https://minecraftfeedback.zendesk.com/api/v2/help_center/en-us/sections/360001185332/articles?per_page=5",
        },
        {
            "name": "article",
            "url": "https://minecraftfeedback.zendesk.com/api/v2/help_center/en-us/sections/360001186971/articles?per_page=5",
        },
    ]
    for section in sections:
        try:
            alist = get_stored_list("scheduler", "mcfeedbacknews")
            get = await get_url(
                section["url"],
                200,
                attempt=1,
                request_private_ip=True,
                logging_err_resp=False,
            )
            res = json.loads(get)
            articles = []
            for i in res["articles"]:
                articles.append(i)
            for article in articles:
                if article["name"] not in alist:
                    name = article["name"]
                    link = article["html_url"]
                    Logger.info(f"Huh, we find {name}.")
                    await JobQueue.trigger_hook_all(
                        "feedback_news",
                        message=MessageChain(
                            [
                                I18NContext(
                                    "minecraft_news.message.feedback_news",
                                    name=name,
                                    link=str(Url(link)),
                                )
                            ]
                        ),
                    )
                    alist.append(name)
                    update_stored_list("scheduler", "mcfeedbacknews", alist)
        except Exception:
            if Config("debug", False):
                Logger.error(traceback.format_exc())
