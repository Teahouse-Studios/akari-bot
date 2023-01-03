import asyncio
import os
import traceback
from datetime import datetime

from config import Config
from core.elements import Plain, Image
from core.logger import Logger
from core.utils import get_url

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
        return {'success': False, 'msg': '查询失败。'}
    except Exception:
        traceback.print_exc()
        return {'success': False, 'msg': '查询失败。'}
    if song_info["status"] == 0:
        msg = []
        difficulties = song_info["content"]["difficulties"]
        if len(difficulties) < diff:
            return [Plain("该谱面难度不存在。")]
        song_name = difficulties[diff]['name_en']
        diff_display_name = 'PRS' if diff == 0 else 'PST' if diff == 1 else 'FTR' if diff == 2 else 'BYD' \
                            if diff == 3 else '???'
        side_display_name = '光芒' if difficulties[diff]['side'] == 0 else '纷争' if difficulties[diff]['side'] == 1 else\
                            '消色' if difficulties[diff]['side'] == 2 else '???'
        msg.append(f'{song_name} ({diff_display_name}/{side_display_name})')
        display_rating_1 = difficulties[diff]['difficulty'] / 2
        display_rating_2 = difficulties[diff]['difficulty'] // 2
        display_rating = str(display_rating_2) + ("+" if display_rating_1 > display_rating_2 else "")
        rating = difficulties[diff]['rating'] / 10
        msg.append('难度：' + display_rating + f' ({rating})')
        msg.append('作曲：' + difficulties[diff]['artist'])
        msg.append('封面：' + difficulties[diff]['jacket_designer'])
        msg.append('谱师：' + difficulties[diff]['chart_designer'])
        msg.append('物量：' + str(difficulties[diff]['note']))
        msg.append('BPM：' + str(difficulties[diff]['bpm']))
        msg.append('所属曲包：' + difficulties[diff]['set_friendly'])
        msg.append('时长：' + str(difficulties[diff]['time']) + '秒')
        msg.append('上架日期：' + datetime.fromtimestamp(difficulties[diff]["date"]).strftime("%Y-%m-%d"))
        msg.append('需要通过世界解锁：' + ('是' if difficulties[diff]['world_unlock'] else '否'))
        msg.append('需要下载：' + ('是' if difficulties[diff]['remote_download'] else '否'))
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

                msg.append('最佳成绩：' + str(score) +
                           f'\n({ptt}, '
                           f'P: {str(getuserinfo["pure_count"])}'
                           f'({str(getuserinfo["shiny_pure_count"])}), '
                           f'F: {str(getuserinfo["far_count"])}, '
                           f'L: {str(getuserinfo["lost_count"])})')

            except Exception:
                traceback.print_exc()
                try:
                    play_info = await get_url(f'{api_url}user/best?usercode={usercode}&songid={song_info["content"]["song_id"]}&'
                                              f'difficulty={diff}',
                                              headers=headers, status_code=200,
                                              fmt='json')
                    if play_info["status"] == 0:
                        msg.append('最佳成绩：' + str(play_info["content"]["record"]["score"]) +
                                   f'\n({str(play_info["content"]["record"]["rating"])}, '
                                   f'P: {str(play_info["content"]["record"]["perfect_count"])}'
                                   f'({str(play_info["content"]["record"]["shiny_perfect_count"])}), '
                                   f'F: {str(play_info["content"]["record"]["near_count"])}, '
                                   f'L: {str(play_info["content"]["record"]["miss_count"])})')
                except Exception:
                    traceback.print_exc()

        return '\n'.join(msg)
    elif song_info['status'] in errcode:
        return Plain(f'查询失败：{errcode[song_info["status"]]}')
    else:
        return Plain('查询失败。' + song_info)








