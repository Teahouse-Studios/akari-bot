import os
import traceback
from datetime import datetime

from config import Config
from core.builtins import Plain
from core.logger import Logger
from core.utils.http import get_url

assets_path = os.path.abspath('./assets/arcaea')
api_url = Config("botarcapi_url")


async def get_song_info(msgsession, sid, diff: int, usercode=None):
    headers = {"User-Agent": Config('botarcapi_agent')}
    try:
        song_info = await get_url(f'{api_url}/song/info?songname={sid}', headers=headers, status_code=200,
                                  fmt='json')
    except ValueError as e:
        Logger.info(f'[{sid}] {e}')
        return {'success': False, 'msg': msgsession.locale.t('arcaea.message.failed')}
    except Exception:
        traceback.print_exc()
        return {'success': False, 'msg': msgsession.locale.t('arcaea.message.failed')}
    if song_info["status"] == 0:
        msg = []
        difficulties = song_info["content"]["difficulties"]
        if len(difficulties) < diff:
            return [Plain(msgsession.locale.t('arcaea.message.song.invalid.difficulty'))]
        song_name = difficulties[diff]['name_en']
        diff_display_name = 'PST' if diff == 0 else 'PRS' if diff == 1 else 'FTR' if diff == 2 else 'BYD' \
            if diff == 3 else '???'
        side_display_name = msgsession.locale.t('arcaea.message.song.side.light') if difficulties[diff]['side'] == 0 else msgsession.locale.t(
            'arcaea.message.song.side.conflict') if difficulties[diff]['side'] == 1 else msgsession.locale.t('arcaea.message.song.side.colorless') if difficulties[diff]['side'] == 2 else '???'
        msg.append(f'{song_name} ({diff_display_name}/{side_display_name})')
        display_rating_1 = difficulties[diff]['difficulty'] / 2
        display_rating_2 = difficulties[diff]['difficulty'] // 2
        display_rating = str(display_rating_2) + ("+" if display_rating_1 > display_rating_2 else "")
        rating = difficulties[diff]['rating'] / 10
        msg.append(msgsession.locale.t('arcaea.message.song.difficulty_rating') + display_rating + f' ({rating})')
        msg.append(msgsession.locale.t('arcaea.message.song.artist') + difficulties[diff]['artist'])
        msg.append(msgsession.locale.t('arcaea.message.song.jacket_designer') + difficulties[diff]['jacket_designer'])
        msg.append(msgsession.locale.t('arcaea.message.song.chart_designer') + difficulties[diff]['chart_designer'])
        msg.append(msgsession.locale.t('arcaea.message.song.note') + str(difficulties[diff]['note']))
        msg.append(msgsession.locale.t('arcaea.message.song.bpm') + str(difficulties[diff]['bpm']))
        msg.append(msgsession.locale.t('arcaea.message.song.set_friendly') + difficulties[diff]['set_friendly'])
        msg.append(msgsession.locale.t('arcaea.message.song.time') +
                   str(difficulties[diff]['time']) +
                   msgsession.locale.t('arcaea.message.song.time.second'))
        msg.append(msgsession.locale.t('arcaea.message.song.date') +
                   datetime.fromtimestamp(difficulties[diff]["date"]).strftime("%Y-%m-%d"))
        msg.append(msgsession.locale.t('arcaea.message.song.world_unlock') +
                   (msgsession.locale.t('yes') if difficulties[diff]['world_unlock'] else msgsession.locale.t('no')))
        msg.append(msgsession.locale.t('arcaea.message.song.remote_download') +
                   (msgsession.locale.t('yes') if difficulties[diff]['remote_download'] else msgsession.locale.t('no')))
        if usercode:
            try:
                play_info = await get_url(
                    f'{api_url}user/best?usercode={usercode}&songid={song_info["content"]["song_id"]}&'
                    f'difficulty={diff}',
                    headers=headers, status_code=200,
                    fmt='json')
                if play_info["status"] == 0:
                    msg.append(msgsession.locale.t('arcaea.message.song.best') +
                               str(play_info["content"]["record"]["score"]) +
                               f'\n({str(play_info["content"]["record"]["rating"])}, '
                               f'P: {str(play_info["content"]["record"]["perfect_count"])}'
                               f'({str(play_info["content"]["record"]["shiny_perfect_count"])}), '
                               f'F: {str(play_info["content"]["record"]["near_count"])}, '
                               f'L: {str(play_info["content"]["record"]["miss_count"])})')
            except Exception:
                traceback.print_exc()

        return '\n'.join(msg)
    else:
        errcode_string = f"arcaea.errcode.{song_info['status']}"
        if locale := msgsession.locale.t(errcode_string) != errcode_string:
            return f'{msgsession.locale.t("arcaea.message.failed.errcode")}{locale}'
        return msgsession.locale.t('arcaea.message.failed') + song_info
