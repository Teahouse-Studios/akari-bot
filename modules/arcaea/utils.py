import os
import shutil
import traceback

from config import Config
from core.utils.http import get_url, download_to_cache
from .initialize import blur_song_img

botarcapi_url = Config("botarcapi_url")
headers = {"User-Agent": Config('botarcapi_agent')}
assets_path = os.path.abspath('./assets')
cache_path = os.path.abspath('./cache')
assets_arc = os.path.abspath(f'{assets_path}/arcaea')

errcode = {-1: msg.locale.t('arcaea.errcode.-1'),
           -2: msg.locale.t('arcaea.errcode.-2'),
           -3: msg.locale.t('arcaea.errcode.-3'),
           -4: msg.locale.t('arcaea.errcode.-4'),
           -5: msg.locale.t('arcaea.errcode.-5'),
           -6: msg.locale.t('arcaea.errcode.-6'),
           -7: msg.locale.t('arcaea.errcode.-7'),
           -8: msg.locale.t('arcaea.errcode.-8'),
           -9: msg.locale.t('arcaea.errcode.-9'),
           -10: msg.locale.t('arcaea.errcode.-10'),
           -11: msg.locale.t('arcaea.errcode.-11'),
           -12: msg.locale.t('arcaea.errcode.-12'),
           -13: msg.locale.t('arcaea.errcode.-13'),
           -14: msg.locale.t('arcaea.errcode.-14'),
           -15: msg.locale.t('arcaea.errcode.-15'),
           -16: msg.locale.t('arcaea.errcode.-16'),
           -17: msg.locale.t('arcaea.errcode.-17'),
           -18: msg.locale.t('arcaea.errcode.-18'),
           -19: msg.locale.t('arcaea.errcode.-19'),
           -20: msg.locale.t('arcaea.errcode.-20'),
           -23: msg.locale.t('arcaea.errcode.-23'),
           -233: msg.locale.t('arcaea.errcode.-233'), }


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
    file = await download_to_cache(
        botarcapi_url + f"assets/song?songid={songid}" + ('&difficulty=3' if has_byd_jacket else ''),
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
