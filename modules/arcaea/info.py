import os

from config import Config
from core.elements import Plain, Image

from core.utils.bot import get_url

assets_path = os.path.abspath('./assets/arcaea')
api_url = Config("arcapi_url")


async def get_info(usercode):
    headers = {"User-Agent": Config('arcapi_agent')}
    try:
        get_ = await get_url(api_url + "user/info?usercode=" + usercode + '&recent=1', headers=headers, fmt='json')
    except Exception:
        return [Plain('查询失败。')]
    print(get_)
    if get_["status"] == 0:
        recent = get_['content']["recent_score"]
        if len(recent) < 0:
            return [Plain('此用户无游玩记录。')]
        recent = recent[0]
        try:
            get_songinfo = await get_url(api_url + "song/info?songname=" + recent['song_id'], headers=headers,
                                         fmt='json')
        except:
            return [Plain('查询失败。')]
        difficulty = '???'
        if recent['difficulty'] == 0:
            difficulty = 'PST'
        if recent['difficulty'] == 1:
            difficulty = 'PRS'
        if recent['difficulty'] == 2:
            difficulty = 'FTR'
        if recent['difficulty'] == 3:
            difficulty = 'BYD'
        trackname = get_songinfo['content']['title_localized']['en']
        imgpath = f'{assets_path}/jacket/{recent["song_id"]}_{recent["difficulty"]}.jpg'
        if not os.path.exists(imgpath):
            imgpath = f'{assets_path}/jacket/{recent["song_id"]}.jpg'
        realptt = get_songinfo['content']['difficulties'][recent['difficulty']]['ratingReal']
        ptt = recent['rating']
        score = recent['score']
        shiny_pure = recent['shiny_perfect_count']
        pure = recent['perfect_count']
        far = recent['near_count']
        lost = recent['miss_count']
        try:
            get_userinfo = await get_url(api_url + "user/info?usercode=" + usercode, headers=headers, fmt='json')
        except:
            return [Plain('查询失败。')]
        username = get_userinfo['content']['name']
        usrptt = int(get_userinfo['content']['rating']) / 100
        result = [Plain(f'{username} (Ptt: {usrptt})的最近游玩记录：\n'
                        f'{trackname} ({difficulty})\n'
                        f'Score: {score}\n'
                        f'Pure: {pure} ({shiny_pure})\n'
                        f'Far: {far}\n'
                        f'Lost: {lost}\n'
                        f'Potential: {realptt} -> {ptt}')]
        if os.path.exists(imgpath):
            result.append(Image(imgpath))
        return result
    elif get_["status"] == -1:
        return [Plain('[-1] 非法的好友码。')]
    elif get_["status"] == -4:
        return [Plain('[-4] 查询失败。')]
    elif get_["status"] == -6:
        return [Plain('[-6] 没有游玩记录。')]
    else:
        return [Plain('查询失败。' + str(get_))]
