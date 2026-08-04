import orjson

from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import I18NContext, Url, Image
from core.component import module
from core.logger import Logger
from core.scheduler import IntervalTrigger
from core.utils.http import get_url
from core.utils.storedata import get_stored_list, update_stored_list
from core.web_render import web_render, SourceOptions, RawOptions

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


startup_mute = (
    True  # flag to prevent news spam on bot startup, will be set to False after the first run of the news check
)


@minecraft_news.schedule(IntervalTrigger(seconds=600))
async def _():
    baseurl = "https://www.minecraft.net"
    global startup_mute
    url = "https://www.minecraft.net/content/minecraftnet/language-masters/en-us/jcr:content/root/container/image_grid_a_copy_64.articles.page-1.json"
    try:
        getpage = await web_render.source(SourceOptions(url=url, raw_text=True))
        if not getpage:
            Logger.error("Failed to fetch Minecraft news page.")
            return
        if getpage:
            alist = await get_stored_list(Bot.Info.client_name, "mcnews")
            o_json = orjson.loads(getpage)
            o_nws = o_json["article_grid"]
            for o_article in o_nws:
                title = o_article["default_tile"]["title"]
                desc = o_article["default_tile"]["sub_header"]
                link = baseurl + o_article["article_url"]
                image = baseurl + o_article["default_tile"]["image"]["imageURL"]
                if title not in alist:
                    Logger.info(f"New Minecraft news found: {title} - {desc} - {link}")
                    if not startup_mute:
                        try:
                            imgb64 = "base64://" + (await web_render.get_raw(RawOptions(url=image)))["data"]
                        except Exception:
                            Logger.exception("Failed to fetch Minecraft news image.")
                            imgb64 = None
                        await Bot.post_message(
                            "minecraft_news",
                            message=MessageChain.assign(
                                [
                                    I18NContext(
                                        "minecraft_news.message.minecraft_news",
                                        title=title,
                                        desc=desc,
                                    ),
                                    Url(link, trusted=True),
                                    Image(imgb64) if imgb64 else None,
                                ]
                            ),
                        )
                    alist.append(title)
                    await update_stored_list(Bot.Info.client_name, "mcnews", alist)
        startup_mute = False
    except Exception:
        Logger.exception()


@feedback_news.schedule(IntervalTrigger(seconds=600))
async def _():
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
            alist = await get_stored_list(Bot.Info.client_name, "mcfeedbacknews")
            get = await get_url(
                section["url"],
                200,
                attempt=1,
                request_private_ip=True,
                logging_err_resp=False,
            )
            res = orjson.loads(get)
            articles = res.get("articles", [])
            for article in articles:
                name = article.get("name", "")
                if name and name not in alist:
                    link = article.get("html_url", "")
                    Logger.info(f"Huh, we find {name}.")
                    await Bot.post_message(
                        "feedback_news",
                        message=MessageChain.assign(
                            [
                                I18NContext(
                                    "minecraft_news.message.feedback_news",
                                    name=name,
                                ),
                                Url(link, trusted=True),
                            ]
                        ),
                    )
                    alist.append(name)
                    await update_stored_list(Bot.Info.client_name, "mcfeedbacknews", alist)
        except Exception:
            Logger.exception()
