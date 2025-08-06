import orjson as json

from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import I18NContext, Url
from core.component import module
from core.config import Config
from core.logger import Logger
from core.scheduler import IntervalTrigger
from core.utils.http import get_url
from core.utils.storedata import get_stored_list, update_stored_list
from core.web_render import web_render, SourceOptions

minecraft_news = module(
    "minecraft_news",
    developers=["_LittleC_", "OasisAkari", "Dianliang233"],
    recommend_modules=["feedback_news"],
    desc="{I18N:minecraft_news.help.minecraft_news}",
    alias=["minecraftnews", "mcnews"],
    doc=True,
    rss=True,
)

feedback_news = module(
    "feedback_news",
    developers=["Dianliang233"],
    recommend_modules=["minecraft_news"],
    desc="{I18N:minecraft_news.help.feedback_news}",
    alias="feedbacknews",
    doc=True,
    rss=True,
)

"""class Article:
    count = 10
    tags = ["minecraft:article/news", "minecraft:article/insider", "minecraft:article/culture",
            "minecraft:article/merch", "minecraft:stockholm/news", "minecraft:stockholm/guides",
            "minecraft:stockholm/deep-dives", "minecraft:stockholm/merch", "minecraft:stockholm/events",
            "minecraft:stockholm/minecraft-builds", "minecraft:stockholm/marketplace"]

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


@minecraft_news.schedule(
    IntervalTrigger(seconds=600)
)
async def _():
    baseurl = "https://www.minecraft.net"
    url = "https://www.minecraft.net/content/minecraftnet/language-masters/en-us/jcr:content/root/container/image_grid_a_copy_64.articles.page-1.json"
    try:
        getpage = await web_render.source(SourceOptions(url=url, raw_text=True))
        if not getpage:
            Logger.error("Failed to fetch Minecraft news page.")
            return
        if getpage:
            alist = await get_stored_list(Bot.Info.client_name, "mcnews")
            o_json = json.loads(getpage)
            o_nws = o_json["article_grid"]
            for o_article in o_nws:
                default_tile = o_article["default_tile"]
                title = default_tile["title"]
                desc = default_tile["sub_header"]
                link = baseurl + o_article["article_url"]
                if title not in alist:
                    await Bot.post_message(
                        "minecraft_news",
                        message=MessageChain.assign(
                            [
                                I18NContext(
                                    "minecraft_news.message.minecraft_news",
                                    title=title,
                                    desc=desc,
                                ),
                                Url(link, use_mm=False)
                            ]
                        ),
                    )
                    alist.append(title)
                    await update_stored_list(Bot.Info.client_name, "mcnews", alist)
    except Exception:
        if Config("debug", False):
            Logger.exception()


@feedback_news.schedule(IntervalTrigger(seconds=600))
async def _():
    sections = [{"name": "beta",
                 "url": "https://minecraftfeedback.zendesk.com/api/v2/help_center/en-us/sections/360001185332/articles?per_page=5",
                 },
                {"name": "article",
                 "url": "https://minecraftfeedback.zendesk.com/api/v2/help_center/en-us/sections/360001186971/articles?per_page=5",
                 },
                ]
    for section in sections:
        try:
            alist = await get_stored_list(Bot.Info.client_name, "mcfeedbacknews")
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
                    await Bot.post_message(
                        "feedback_news",
                        message=MessageChain.assign(
                            [
                                I18NContext(
                                    "minecraft_news.message.feedback_news",
                                    name=name,
                                ), Url(link, use_mm=False)
                            ]
                        ),
                    )
                    alist.append(name)
                    await update_stored_list(Bot.Info.client_name, "mcfeedbacknews", alist)
        except Exception:
            if Config("debug", False):
                Logger.exception()
