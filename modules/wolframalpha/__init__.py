import os
import urllib.parse
from PIL import Image

from config import Config
from core.builtins import Bot, Image as BImage
from core.component import module
from core.dirty_check import rickroll
from core.exceptions import ConfigValueError
from core.utils.http import download_to_cache, get_url
from .check import safe_check


appid = Config('wolfram_alpha_appid')

w = module(
    'wolframalpha',
    alias=['wolfram', 'wa'],
    developers=['DoroWolf'],
    desc='{wolframalpha.help.desc}',
    support_languages=['en_us'])


@w.handle('<query> {{wolframalpha.help}}')
async def _(msg: Bot.MessageSession, query: str):
    if await safe_check(query):
        await msg.finish(rickroll(msg))
    url_query = urllib.parse.quote(query)
    if not appid:
        raise ConfigValueError(msg.locale.t('error.config.secret.not_found'))
    url = f"http://api.wolframalpha.com/v1/simple?appid={appid}&i={url_query}&units=metric"

    try:
        img_path = await download_to_cache(url, status_code=200)
        if img_path:
            with Image.open(img_path) as img:
                output = os.path.splitext(img_path)[0] + ".png"
                img.save(output, "PNG")
            os.remove(img_path)
            await msg.finish([BImage(output)])
    except ValueError as e:
        if str(e).startswith('501'):
            await msg.finish(msg.locale.t('wolframalpha.message.incomprehensible'))


@w.handle('ask <question> {{wolframalpha.help.ask}}')
async def _(msg: Bot.MessageSession, question: str):
    if await safe_check(question):
        await msg.finish(rickroll(msg))
    url_query = urllib.parse.quote(question)
    if not appid:
        raise ConfigValueError(msg.locale.t('error.config.secret.not_found'))
    url = f"http://api.wolframalpha.com/v1/result?appid={appid}&i={url_query}&units=metric"
    try:
        data = await get_url(url, 200)
        if await check_bool(data):
            await msg.finish(rickroll(msg))
        await msg.finish(data)
    except ValueError as e:
        if str(e).startswith('501'):
            await msg.finish(msg.locale.t('wolframalpha.message.incomprehensible'))
