from core.builtins import Bot
from core.component import module

minecraft_news = module('minecraft_news', developers=['_LittleC_', 'OasisAkari', 'Dianliang233'],
                        recommend_modules=['feedback_news'],
                        desc='{minecraft_news.help.minecraft_news}', doc=True, alias='minecraftnews')


@minecraft_news.hook()
async def start_check_news(fetch: Bot.FetchTarget, ctx: Bot.ModuleHookContext):
    await fetch.post_message('minecraft_news', **ctx.args)


feedback_news = module('feedback_news', developers=['Dianliang233'], recommend_modules=['minecraft_news'],
                       desc='{minecraft_news.help.feedback_news}', doc=True,
                       alias='feedbacknews')


@feedback_news.hook()
async def feedback_news(fetch: Bot.FetchTarget, ctx: Bot.ModuleHookContext):
    await fetch.post_message('feedback_news', **ctx.args)
