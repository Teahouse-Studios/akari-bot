import traceback
from typing import List, Optional

import emoji

from config import Config
from core.builtins import Bot, Image
from core.component import module
from core.logger import Logger
from core.utils.http import get_url
from .emoji_data import dates, emojis


API = "https://www.gstatic.com/android/keyboard/emojikitchen/"


emojimix = module('emojimix', developers=['MeetWq', 'DoroWolf'])


@emojimix.handle('<emoji1> <emoji2> {{emojimix.help}}')
async def _(msg: Bot.MessageSession, emoji1: str, emoji2: str):
    if not (check_valid_emoji(emoji1) and check_valid_emoji(emoji2)):
        await msg.finish(msg.locale.t("emojimix.message.invalid"))
    if not (check_composite_emoji(emoji1) and check_composite_emoji(emoji2)):
        await msg.finish(msg.locale.t("emojimix.message.composite_emoji"))
        
    result = await mix_emoji(msg, emoji1, emoji2)
    await msg.finish(Image(result))


def check_valid_emoji(str):
    return emoji.is_emoji(str)

def check_composite_emoji(str):
    return len(str) == 1


def create_url(date: str, emoji1: List[int], emoji2: List[int]) -> str:
    def emoji_code(emoji: List[int]):
        return "-".join(f"u{c:x}" for c in emoji)

    u1 = emoji_code(emoji1)
    u2 = emoji_code(emoji2)
    return f"{API}{date}/{u1}/{u1}_{u2}.png"


def find_emoji(emoji_code: str) -> Optional[List[int]]:
    emoji_num = ord(emoji_code)
    for e in emojis:
        if emoji_num in e:
            return e
    return None


async def mix_emoji(msg: Bot.MessageSession, emoji1: str, emoji2: str) -> Optional[str]:
    emoji_code1 = find_emoji(emoji1)
    emoji_code2 = find_emoji(emoji2)
    if not emoji_code1:
        await msg.finish(msg.locale.t("emojimix.message.unsupported") + emoji1)
    if not emoji_code2:
        await msg.finish(msg.locale.t("emojimix.message.unsupported") + emoji2)

    urls: List[str] = []
    for date in dates:
        urls.append(create_url(date, emoji_code1, emoji_code2))
        urls.append(create_url(date, emoji_code2, emoji_code1))

        for url in urls:
            try:
                await get_url(url, 200, fmt='read', logging_err_resp=False)
                return url
            except ValueError:
                if Config('debug', False):
                    Logger.error(traceback.format_exc())
                pass
        await msg.finish(msg.locale.t("emojimix.message.not_found"))