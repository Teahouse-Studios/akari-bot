import os
import shutil
import traceback

from config import Config
from core.utils import get_url, download_to_cache
from .initialize import blur_song_img

botarcapi_url = Config("botarcapi_url")
headers = {"User-Agent": Config('botarcapi_agent')}
assets_path = os.path.abspath('./assets')
cache_path = os.path.abspath('./cache')
assets_arc = os.path.abspath(f'{assets_path}/arcaea')


errcode = {-1: "非法的用户名或好友代码",
           -2: "非法的好友代码",
           -3: "未找到用户",
           -4: "好友列表已满",
           -5: "非法的歌曲名或歌曲ID",
           -6: "非法的歌曲ID",
           -7: "歌曲未记录",
           -8: "记录过多",
           -9: "非法的难度",
           -10: "非法的近期记录数",
           -11: "分配Arcaea账户失败",
           -12: "清除好友对象失败",
           -13: "添加对象失败",
           -14: "该歌曲无Beyond难度",
           -15: "无游玩记录",
           -16: "用户排行榜被封禁",
           -17: "查询B30记录失败",
           -18: "更新服务器不可用",
           -19: "非法的搭档",
           -20: "文件不存在",
           -23: "发生了内部错误",
           -233: "发生了未知错误", }


async def get_userinfo(user):
    try:
        get_ = await get_url(botarcapi_url + f"user/info?user={user}", status_code=200, headers=headers, fmt='json')
        username = get_['content']['account_info']['name']
        code = get_['content']['account_info']['code']
        return username, code
    except Exception:
        traceback.print_exc()
        return False


async def autofix_b30_song_background(songid, byd=False):
    has_byd_jacket = False
    if byd:
        try:
            get_ = await get_url(botarcapi_url + f"song/info?songid={songid}", status_code=200, headers=headers,
                                 fmt='json')
            difficulties = get_['content']['difficulties']
            if len(difficulties) == 4:
                if difficulties[3]['jacket_override']:
                    has_byd_jacket = True
        except Exception:
            traceback.print_exc()
    file_name = f"{songid}{'_3' if has_byd_jacket else ''}.jpg"
    file = await download_to_cache(botarcapi_url + f"assets/song?songid={songid}" + ('&difficulty=3' if has_byd_jacket else ''),
                                   headers=headers)
    if file:
        dst = assets_arc + '/jacket/'
        shutil.copyfile(file, dst + file_name)
        await blur_song_img(dst + file_name)


async def autofix_character(partner):
    file = await download_to_cache(botarcapi_url + f"assets/char?partner={partner}",
                                   headers=headers)
    if file:
        dst = assets_arc + '/char/'
        shutil.copyfile(file, dst + f"{partner}.png")
