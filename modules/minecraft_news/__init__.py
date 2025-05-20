from core.builtins import Bot
from core.component import module

minecraft_news = module(
    "minecraft_news",
    developers=["_LittleC_", "OasisAkari", "Dianliang233"],
    recommend_modules=["feedback_news"],
    desc="[I18N:minecraft_news.help.minecraft_news]",
    alias=["minecraftnews", "mcnews"],
    doc=True,
    rss=True,
)


@minecraft_news.hook()
async def _(fetch: Bot.FetchTarget, ctx: Bot.ModuleHookContext):
    await fetch.post_message("minecraft_news", **ctx.args)


feedback_news = module(
    "feedback_news",
    developers=["Dianliang233"],
    recommend_modules=["minecraft_news"],
    desc="[I18N:minecraft_news.help.feedback_news]",
    alias="feedbacknews",
    doc=True,
    rss=True,
)


@feedback_news.hook()
async def _(fetch: Bot.FetchTarget, ctx: Bot.ModuleHookContext):
    await fetch.post_message("feedback_news", **ctx.args)
