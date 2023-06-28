import ujson as json
import os

from core.builtins import ErrorMessage
from core.utils.http import get_url, post_url
from .maimaidx_music import get_cover_len5_id

async def get_alias(input, get_music=False):
    url = "https://download.fanyu.site/maimai/alias.json"
    data = await get_url(url, 200, fmt='json')

    result = []
    if get_music:
        if input in data:
            result = data[input]
    else:
        input = input.replace("_", " ")
        for alias, ids in data.items():
            if input in ids:
                result.append(alias)

    return result


async def get_record(msg, payload):
    url = f"https://www.diving-fish.com/api/maimaidxprober/query/player"
    try:
        data = await post_url(url,
                              data=json.dumps(payload),
                              status_code=200,
                              headers={'Content-Type': 'application/json', 'accept': '*/*'}, fmt='json')
    except ValueError as e:
        if str(e).startswith('400'):
            await msg.finish(msg.locale.t("maimai.message.user_not_found"))
        if str(e).startswith('403'):
            await msg.finish(msg.locale.t("maimai.message.forbidden"))
        else:
            await msg.finish(ErrorMessage(str(e)))

    return data


async def get_plate(msg, payload):
    url = f"https://www.diving-fish.com/api/maimaidxprober/query/plate"
    try:
        data = await post_url(url,
                              data=json.dumps(payload),
                              status_code=200,
                              headers={'Content-Type': 'application/json', 'accept': '*/*'}, fmt='json')
    except ValueError as e:
        if str(e).startswith('400'):
            await msg.finish(msg.locale.t("maimai.message.user_not_found"))
        if str(e).startswith('403'):
            await msg.finish(msg.locale.t("maimai.message.forbidden"))
        else:
            await msg.finish(ErrorMessage(str(e)))

    return data

def get_cover(sid):
    cover_url = f"https://www.diving-fish.com/covers/{get_cover_len5_id(sid)}.png"
    cover_dir = f"./assets/maimai/static/mai/cover/"
    cover_path = cover_dir + f'{get_cover_len5_id(sid)}.png'
    if sid == '11364':
        return os.path.abspath(cover_path)
    else:
        return cover_url
