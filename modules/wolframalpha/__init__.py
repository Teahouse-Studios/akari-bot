import os
import urllib.parse

from config import Config
from core.builtins import Bot, Image as BImage
from core.component import module
from core.utils.http import download_to_cache, get_url
from core.dirty_check import check_bool, rickroll
from PIL import Image

appid = Config('wolfram_alpha_appid')

w = module(
    'wolframalpha',
    alias=['wolfram', 'wa'],
    developers=['DoroWolf'],
    desc='{wolframalpha.help.desc}',
    support_languages=['en_us'])


@w.handle('<query> {{wolframalpha.help}}')
async def _(msg: Bot.MessageSession):
    query = msg.parsed_msg['<query>']
    if await check_bool(query):
        query = rickroll()
        await msg.finish(query)
    url_query = urllib.parse.quote(query)
    if not appid:
        raise Exception(msg.locale.t('error.config.secret'))
    url = f"http://api.wolframalpha.com/v1/simple?appid={appid}&i={url_query}&units=metric"

    try:
        img_path = await download_to_cache(url, status_code=200)
        if img_path:
            img = Image.open(img_path)
            output = os.path.splitext(img_path)[0] + ".png"
            img.save(output, "PNG")
            os.remove(img_path)
            await msg.finish([BImage(output)])
    except ValueError as e:
        if str(e).startswith('501'):
            await msg.finish(msg.locale.t(' wolframalpha.message.incomprehensible'))


@w.handle('ask <question> {{wolframalpha.help.ask}}')
async def _(msg: Bot.MessageSession):
    query = msg.parsed_msg['<question>']
    if await check_bool(query):
        query = rickroll()
        await msg.finish(query)
    url_query = urllib.parse.quote(query)
    if not appid:
        raise Exception(msg.locale.t('error.config.secret'))
    url = f"http://api.wolframalpha.com/v1/result?appid={appid}&i={url_query}&units=metric"
    try:
        data = await get_url(url, 200)
        if await check_bool(data):
            data = rickroll()
        await msg.finish(data)
    except ValueError as e:
        if str(e).startswith('501'):
            await msg.finish(msg.locale.t('wolframalpha.message.incomprehensible'))
