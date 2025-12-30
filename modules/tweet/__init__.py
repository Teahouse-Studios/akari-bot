import orjson

from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext, Url
from core.component import module
from core.dirty_check import check_bool, rickroll
from core.utils.http import get_url
from core.utils.image import cb64imglst
from core.utils.tools import is_int
from core.web_render import web_render, ElementScreenshotOptions

t = module(
    "tweet",
    developers=["Dianliang233"],
    desc="{I18N:tweet.help.desc}",
    doc=True,
    alias=["x"],
)


@t.command("<tweet> {{I18N:tweet.help}}")
async def _(msg: Bot.MessageSession, tweet: int):
    await get_tweet(msg, tweet)


@t.regex(r"(?:http[s]?:\/\/)?(?:www\.)?(?:twitter|x)\.com\/\S+\/status\/(\d+)",
         mode="M",
         desc="{I18N:tweet.help.regex.url}",
         show_typing=False,
         )
async def _(msg: Bot.MessageSession):
    tweet = msg.matched_msg.group(1)
    if is_int(tweet):
        await get_tweet(msg, int(tweet))


async def get_tweet(msg: Bot.MessageSession, tweet_id: int):
    try:
        res = await get_url(f"https://react-tweet.vercel.app/api/tweet/{tweet_id}", 200)
    except ValueError as e:
        if str(e).startswith("404"):
            await msg.finish(I18NContext("tweet.message.not_found"))
        else:
            raise e

    res_json = orjson.loads(res)
    if await check_bool("\n".join(
            [res_json["data"]["text"], res_json["data"]["user"]["name"], res_json["data"]["user"]["screen_name"]]), msg):
        await msg.finish(rickroll())

    css = """
        main {
            justify-content: start !important;
        }

        main > div {
            margin: 0 !important;
            border: 0 !important;
        }

        article {
            padding: .75rem 1rem;
        }

        footer {
            display: none;
        }

        #__next > div {
            height: auto;
            padding: 0;
        }

        a[href^="https://x.com/intent/follow"],
        a[href^="https://help.x.com/en/x-for-websites-ads-info-and-privacy"],
        div[class^="tweet-replies"],
        button[aria-label="Copy link"],
        a[aria-label="Reply to this Tweet on Twitter"],
        span[class^="tweet-header_separator"] {
            display: none;
        }
    """

    load_img = await web_render.element_screenshot(ElementScreenshotOptions(
        url=f"https://react-tweet-next.vercel.app/light/{tweet_id}",
        css=css,
        element="article"))
    img_lst = cb64imglst(load_img, bot_img=True)
    img_lst.append(
        Url(
            f"https://x.com/{res_json["data"]["user"]["screen_name"]}/status/{tweet_id}"
        )
    )
    await msg.finish(img_lst)
