import asyncio
import urllib.parse

from config import Config
from core.builtins import Bot, Image
from core.component import module
from core.utils.http import get_url
from core.dirty_check import check_bool, rickroll

appid = Config('wolfram_alpha_appid')

w = module(
    'wolframalpha',
    alias='wolfram',
    developers=['Dianliang233'],
    desc='{wolframalpha.help.desc}',
    support_languages=['en_us'])


@w.handle('<query> {{wolframalpha.help}}')
async def _(msg: Bot.MessageSession):
    query = msg.parsed_msg['<query>']
    url_query = urllib.parse.quote(query.replace(' ', '+'))
    if not appid:
        raise Exception(msg.locale.t('error.config.secret'))
    url = "http://api.wolframalpha.com/v1/simple?appid={appid}&i={url_query}&units=metric"
    
    img = await get_url(url, 200)
    await msg.finish([Image(img)])
