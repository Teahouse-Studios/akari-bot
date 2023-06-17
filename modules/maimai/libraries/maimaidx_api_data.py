import ujson as json

from core.builtins import ErrorMessage
from core.utils.http import get_url, post_url


async def get_alias(input, get_music=False):
    url = f"https://download.fanyu.site/maimai/alias.json"
    data = await get_url(url, 200, fmt='json')

    result = []

    if get_music:
        if input in data:
            result = data[input]
    else:
        result = list(data.keys())

    return result


async def get_rank(msg, payload):
    try:
        userdata = await post_url('https://www.diving-fish.com/api/maimaidxprober/query/player',
                                  data=json.dumps(payload),
                                  status_code=200,
                                  headers={'Content-Type': 'application/json', 'accept': '*/*'}, fmt='json')
        username = userdata['username']
        rating = userdata['rating']
    except ValueError as e:
        if str(e).startswith('400'):
            await msg.finish(msg.locale.t("maimai.message.user_not_found"))
        if str(e).startswith('403'):
            await msg.finish(msg.locale.t("maimai.message.forbidden"))
        else:
            await msg.sendMessage(ErrorMessage(str(e)))

    data = await get_url('https://www.diving-fish.com/api/maimaidxprober/rating_ranking', 200, fmt='json')
    sorted_data = sorted(data, key=lambda x: x['ra'], reverse=True)

    rank = None
    total_rating = 0

    for i, scoreboard in enumerate(sorted_data):
        if scoreboard['username'] == username:
            rank = i + 1
        total_rating += scoreboard['ra']

    average_rating = total_rating / len(sorted_data)

    if rank is None:
        rank = 0

    surpassing_rate = (len(sorted_data) - rank) / len(sorted_data) * 100

    return username, rating, rank, average_rating, surpassing_rate
