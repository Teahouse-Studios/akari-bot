import base64
from io import BytesIO

import orjson as json
from PIL import Image as PILImage

from core.builtins import Bot
from core.builtins.message import Image, Url
from core.component import module
from core.dirty_check import check_bool, rickroll
from core.utils.http import download, get_url
from core.utils.text import isint
from core.utils.web_render import webrender

t = module(
    "tweet",
    developers=["Dianliang233"],
    desc="{tweet.help.desc}",
    doc=True,
    alias=["x"],
)


@t.command("<tweet> {{tweet.help}}")
async def _(msg: Bot.MessageSession, tweet: int):
    await get_tweet(msg, tweet)


@t.regex(r"(?:http[s]?:\/\/)?(?:www\.)?(?:twitter|x)\.com\/\S+\/status\/(\d+)",
         mode="M",
         desc="{tweet.help.regex.url}",
         show_typing=False,
         text_only=False
         )
async def _(msg: Bot.MessageSession):
    tweet = msg.matched_msg.group(1)
    if isint(tweet):
        await get_tweet(msg, int(tweet))


async def get_tweet(msg: Bot.MessageSession, tweet_id: int):
    web_render = webrender("element_screenshot")
    if not web_render:
        await msg.finish(msg.locale.t("error.config.webrender.invalid"))

    try:
        res = await get_url(f"https://react-tweet.vercel.app/api/tweet/{tweet_id}", 200)
    except ValueError as e:
        if str(e).startswith("404"):
            await msg.finish(msg.locale.t("tweet.message.not_found"))
        else:
            raise e

    res_json = json.loads(res)
    if await check_bool(
        res_json["data"]["text"],
        res_json["data"]["user"]["name"],
        res_json["data"]["user"]["screen_name"],
    ):
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

    pic = await download(
        web_render,
        method="POST",
        headers={
            "Content-Type": "application/json",
        },
        post_data=json.dumps(
            {
                "url": f"https://react-tweet-next.vercel.app/light/{tweet_id}",
                "css": css,
                "mw": False,
                "element": "article",
            }
        ),
        request_private_ip=True,
    )
    with open(pic, "rb") as read:
        load_img = json.loads(read.read())
    img_lst = []
    for x in load_img:
        b = base64.b64decode(x)
        bio = BytesIO(b)
        bimg = PILImage.open(bio)
        img_lst.append(Image(bimg))
    img_lst.append(
        Url(
            f"https://x.com/{res_json["data"]["user"]["screen_name"]}/status/{tweet_id}"
        )
    )
    await msg.finish(img_lst)
