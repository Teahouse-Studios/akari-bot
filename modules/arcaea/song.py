import os
import traceback
from datetime import datetime

from config import Config
from core.builtins import Plain
from core.logger import Logger
from core.utils.http import get_url
from .utils import errcode

assets_path = os.path.abspath('./assets/arcaea')
api_url = Config("botarcapi_url")
api_url_official = Config('arcapi_official_url')
headers_official = {'Authorization': Config('arcapi_official_token')}


async def get_song_info(sid, diff: int, usercode=None):
    headers = {"User-Agent": Config('botarcapi_agent')}
    try:
        song_info = await get_url(f'{api_url}song/info?songname={sid}', headers=headers, status_code=200,
                                  fmt='json')
    except ValueError as e:
        Logger.info(f'[{sid}] {e}')
        return {'success': False, 'msg': msg.locale.t('arcaea.message.failed')}
    except Exception:
        traceback.print_exc()
        return {'success': False, 'msg': msg.locale.t('arcaea.message.failed')}
    if song_info["status"] == 0:
        msg = []
        difficulties = song_info["content"]["difficulties"]
        if len(difficulties) < diff:
            return [Plain(msg.locale.t('arcaea.song.message.invalid.difficulty'))]
        song_name = difficulties[diff]['name_en']
        diff_display_name = 'PRS' if diff == 0 else 'PST' if diff == 1 else 'FTR' if diff == 2 else 'BYD' \
            if diff == 3 else '???'
        side_display_name = msg.locale.t('arcaea.song.message.side.light') if difficulties[diff]['side'] == 0 else msg.locale.t('arcaea.song.message.side.conflict') if difficulties[diff][
                                                                                         'side'] == 1 else \
            msg.locale.t('arcaea.song.message.side.colorless') if difficulties[diff]['side'] == 2 else '???'
        msg.append(f'{song_name} ({diff_display_name}/{side_display_name})')
        display_rating_1 = difficulties[diff]['difficulty'] / 2
        display_rating_2 = difficulties[diff]['difficulty'] // 2
        display_rating = str(display_rating_2) + ("+" if display_rating_1 > display_rating_2 else "")
        rating = difficulties[diff]['rating'] / 10
        msg.append(msg.locale.t('arcaea.song.message.difficulty_rating') + display_rating + f' ({rating})')
        msg.append(msg.locale.t('arcaea.song.message.artist') + difficulties[diff]['artist'])
        msg.append(msg.locale.t('arcaea.song.message.jacket_designer') + difficulties[diff]['jacket_designer'])
        msg.append(msg.locale.t('arcaea.song.message.chart_designer') + difficulties[diff]['chart_designer'])
        msg.append(msg.locale.t('arcaea.song.message.note') + str(difficulties[diff]['note']))
        msg.append(msg.locale.t('arcaea.song.message.bpm') + str(difficulties[diff]['bpm']))
        msg.append(msg.locale.t('arcaea.song.message.set_friendly') + difficulties[diff]['set_friendly'])
        msg.append(msg.locale.t('arcaea.song.message.time') + str(difficulties[diff]['time']) + msg.locale.t('arcaea.song.message.time.second'))
        msg.append(msg.locale.t('arcaea.song.message.date') + datetime.fromtimestamp(difficulties[diff]["date"]).strftime("%Y-%m-%d"))
        msg.append(msg.locale.t('arcaea.song.message.world_unlock') + (msg.locale.t('yes') if difficulties[diff]['world_unlock'] else msg.locale.t('no')))
        msg.append(msg.locale.t('arcaea.song.message.remote_download') + (msg.locale.t('yes') if difficulties[diff]['remote_download'] else msg.locale.t('no')))
        if usercode:
            try:
                getuserinfo_json = await get_url(f'{api_url_official}user/{usercode}/score?'
                                                 f'song_id={song_info["content"]["song_id"]}&difficulty={diff}',
                                                 headers=headers_official, status_code=200,
                                                 fmt='json')
                getuserinfo = getuserinfo_json['data']
                score = getuserinfo["score"]
                ptt = rating
                if score >= 10000000:
                    ptt += 2
                elif score >= 9800000:
                    ptt += 1 + (score - 9800000) / 200000
                elif score <= 9500000:
                    ptt += (score - 9500000) / 300000

                msg.append(msg.locale.t('arcaea.song.message.best') + str(score) +
                           f'\n({ptt}, '
                           f'P: {str(getuserinfo["pure_count"])}'
                           f'({str(getuserinfo["shiny_pure_count"])}), '
                           f'F: {str(getuserinfo["far_count"])}, '
                           f'L: {str(getuserinfo["lost_count"])})')

            except Exception:
                traceback.print_exc()
                try:
                    play_info = await get_url(
                        f'{api_url}user/best?usercode={usercode}&songid={song_info["content"]["song_id"]}&'
                        f'difficulty={diff}',
                        headers=headers, status_code=200,
                        fmt='json')
                    if play_info["status"] == 0:
                        msg.append(msg.locale.t('arcaea.song.message.best') + str(play_info["content"]["record"]["score"]) +
                                   f'\n({str(play_info["content"]["record"]["rating"])}, '
                                   f'P: {str(play_info["content"]["record"]["perfect_count"])}'
                                   f'({str(play_info["content"]["record"]["shiny_perfect_count"])}), '
                                   f'F: {str(play_info["content"]["record"]["near_count"])}, '
                                   f'L: {str(play_info["content"]["record"]["miss_count"])})')
                except Exception:
                    traceback.print_exc()

        return '\n'.join(msg)
    elif song_info['status'] in errcode:
        return Plain(f{msg.locale.t("arcaea.message.failed.errcode")}{errcode[song_info["status"]]}')
    else:
        return Plain(msg.locale.t('arcaea.message.failed') + song_info)
