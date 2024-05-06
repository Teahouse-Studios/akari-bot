import traceback
from datetime import datetime

import ujson as json

from config import Config
from core.builtins import Bot
from core.exceptions import ConfigValueError
from core.utils.http import get_url


def second2dhm(seconds: int):
    days = seconds // (24 * 3600)
    hours = (seconds % (24 * 3600)) // 3600
    minutes = (seconds % 3600) // 60
    return f"{days}d{hours}h{minutes}m"


async def osu_profile(msg: Bot.MessageSession, uid, mode):
    if not Config('osu_api_key', cfg_type=str):
        raise ConfigValueError(msg.locale.t('error.config.secret.not_found'))
    profile_url = f"https://osu.ppy.sh/api/get_user?k={Config('osu_api_key', cfg_type=str)}&u={uid}&m={mode}"
    try:
        profile = json.loads(await get_url(profile_url, 200))[0]

        userid = profile['user_id']
        username = profile['username']
        country = profile['country']
        level = int(float(profile['level']))
        join_date = datetime.strptime(profile['join_date'], "%Y-%m-%d %H:%M:%S").timestamp()
        join_date = msg.ts2strftime(join_date, iso=True, timezone=False)
        total_seconds_played = int(profile['total_seconds_played'])
        total_play_time = second2dhm(total_seconds_played)
        playcount = profile['playcount']
        accuracy = profile['accuracy']
        pp_raw = profile['pp_raw']
        ranked_score = profile['ranked_score']
        total_score = profile['total_score']
        count300 = int(profile['count300'])
        count100 = int(profile['count100'])
        count50 = int(profile['count50'])
        total_hits = str(count300 + count100 + count50)
        pp_rank = profile['pp_rank']
        pp_country_rank = profile['pp_country_rank']

        grade_t = []
        ss = profile['count_rank_ss']
        if ss:
            grade_t.append(f'SS: {ss}')
        ssh = profile['count_rank_ssh']
        if ssh:
            grade_t.append(f'SSh: {ssh}')
        s = profile['count_rank_s']
        if s:
            grade_t.append(f'S: {s}')
        sh = profile['count_rank_sh']
        if sh:
            grade_t.append(f'Sh: {sh}')
        a = profile['count_rank_a']
        if a:
            grade_t.append(f'A: {a}')
    except BaseException:
        if Config('debug', False):
            traceback.print_exc()
        await msg.finish(msg.locale.t('osu.message.not_found'))

    text = f'UID: {userid}\n' + \
           f'Username: {username}\n' + \
           f'Country: {country}\n' + \
           f'Level: {level}\n' + \
           f'Join Date: {join_date}\n' + \
           f'Total Play Time: {total_play_time}\n' + \
           f'Play Count: {playcount}\n' + \
           f'Hit Accuracy: {round(float(accuracy), 2)}%\n' + \
           f'Performance Point: {pp_raw}\n' + \
           f'Ranked Score: {ranked_score}\n' + \
           f'Total Score: {total_score}\n' + \
           f'Total Hits: {total_hits}\n' + \
           f'Global Ranking: #{pp_rank}\n' + \
           f'Country Ranking: #{pp_country_rank}\n' + \
           f'Grade: {", ".join(grade_t)}'
    await msg.finish(text)
