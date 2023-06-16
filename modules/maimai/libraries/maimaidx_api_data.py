from core.utils.http import get_url

async def get_alias(input, get_music = False):
    url = f"https://download.fanyu.site/maimai/alias.json"
    data = await get_url(url, 200, fmt='json')

    result = []
    
    if get_music:
        if input in data:
            result = data[input]
    else:
        result = list(data.keys())
            
    return result

async def get_rank(msg, player):
    url = f"https://www.diving-fish.com/api/maimaidxprober/rating_ranking"
    data = await get_url(url, 200, fmt='json')

    rate = None
    rank = None
    total_rate = 0

    sorted_data = sorted(data, key=lambda x: x['ra'], reverse=True)

    for i, scoreboard in enumerate(sorted_data):
        if scoreboard['username'].lower() == player.lower():
            username = scoreboard['username']
            rate = scoreboard['ra']
            rank = i + 1
        total_rate += scoreboard['ra']

    average_rate = total_rate / len(sorted_data)

    if rank is None:
        rank = 0

    surpassing_rate = (len(sorted_data) - rank) / len(sorted_data) * 100

    if rate is None:
        await msg.finish(msg.locale.t('maimai.message.user_not_found'))
        return None
            
    return username, rate, rank, average_rate, surpassing_rate