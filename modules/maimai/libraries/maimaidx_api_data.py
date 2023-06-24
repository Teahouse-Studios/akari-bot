import ujson as json

from core.builtins import ErrorMessage
from core.utils.http import get_url, post_url


async def get_alias(input, get_music=False):
    url = "https://download.fanyu.site/maimai/alias.json"
    data = await get_url(url, 200, fmt='json')

    result = []
    if get_music:
        if input in data:
            result = data[input]
    else:
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
