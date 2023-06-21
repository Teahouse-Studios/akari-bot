from datetime import datetime

from core.utils.http import get_url
from .maimaidx_api_data import get_record, get_plate
from .maimaidx_music import TotalList

total_list = TotalList()

achievementList = [50.0, 60.0, 70.0, 75.0, 80.0, 90.0, 94.0, 97.0, 98.0, 99.0, 99.5, 100.0, 100.5]

plate_to_version = {
    '初': 'maimai',
    '真': 'maimai PLUS',
    '超': 'maimai GreeN',
    '檄': 'maimai GreeN PLUS',
    '橙': 'maimai ORANGE',
    '暁': 'maimai ORANGE PLUS',
    '晓': 'maimai ORANGE PLUS',
    '桃': 'maimai PiNK',
    '櫻': 'maimai PiNK PLUS',
    '樱': 'maimai PiNK PLUS',
    '紫': 'maimai MURASAKi',
    '菫': 'maimai MURASAKi PLUS',
    '堇': 'maimai MURASAKi PLUS',
    '白': 'maimai MiLK',
    '雪': 'MiLK PLUS',
    '輝': 'maimai FiNALE',
    '辉': 'maimai FiNALE',
    '熊': 'maimai でらっくす',
    '華': 'maimai でらっくす PLUS',
    '华': 'maimai でらっくす PLUS',
    '爽': 'maimai でらっくす Splash',
    '煌': 'maimai でらっくす Splash PLUS',
    '宙': 'maimai でらっくす UNiVERSE',
    '星': 'maimai でらっくす UNiVERSE PLUS',
    '祭': 'maimai でらっくす FESTiVAL',
    'fesp': 'maimai でらっくす FESTiVAL PLUS'
}

score_to_rank = {
    (0.0, 50.0): "D",
    (50.0, 60.0): "C",
    (60.0, 70.0): "B",
    (70.0, 75.0): "BB",
    (75.0, 80.0): "BBB",
    (80.0, 90.0): "A",
    (90.0, 94.0): "AA",
    (94.0, 97.0): "AAA",
    (97.0, 98.0): "S",
    (98.0, 99.0): "S+",
    (99.0, 99.5): "SS",
    (99.5, 100.0): "SS+",
    (100.0, 100.5): "SSS",
    (100.5, float('inf')): "SSS+",
}

combo_conversion = {
    "fc": "FC",
    "fcp": "FC+",
    "ap": "AP",
    "app": "AP+",
}

sync_conversion = {
    "fs": "FS",
    "fsp": "FS+",
    "fsd": "FDX",
    "fsdp": "FDX+",
}

diffs = {
    0: "Basic",
    1: "Advanced",
    2: "Expert",
    3: "Master",
    4: "Re:MASTER",
}

scoreRank = ['d', 'c', 'b', 'bb', 'bbb', 'a', 'aa', 'aaa', 's', 's+', 'ss', 'ss+', 'sss', 'sss+']
levelList = ['1', '2', '3', '4', '5', '6', '7', '7+', '8', '8+', '9', '9+', '10', '10+', '11', '11+', '12', '12+', '13', '13+', '14', '14+', '15']

async def get_rank(msg, payload):
    player_data = await get_record(msg, payload)

    username = player_data['username']
    rating = player_data['rating']
    url = f"https://www.diving-fish.com/api/maimaidxprober/rating_ranking"
    rank_data = await get_url(url, 200, fmt='json')
    sorted_data = sorted(rank_data, key=lambda x: x['ra'], reverse=True)

    rank = None
    total_rating = 0
    total_rank = len(sorted_data)

    for i, scoreboard in enumerate(sorted_data):
        if scoreboard['username'] == username:
            rank = i + 1
        total_rating += scoreboard['ra']

    if rank is None:
        rank = total_rank

    average_rating = total_rating / total_rank
    surpassing_rate = (total_rank - rank) / total_rank * 100
    time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return time, total_rank, average_rating, username, rating, rank, surpassing_rate


async def get_player_score(msg, payload, input_id):
    payload['version'] = list(set(version for version in plate_to_version.values()))
    res = await get_plate(msg, payload)
    verlist = res["verlist"]
    music = (await total_list.get()).by_id(input_id)
    level_scores = {level: [] for level in range(len(music['level']))}

    for entry in verlist:
        sid = entry["id"]
        achievements = entry["achievements"]
        fc = entry["fc"]
        fs = entry["fs"]
        level_index = entry["level_index"]

        if str(sid) == input_id:
            score_rank = next(
                rank for interval, rank in score_to_rank.items() if interval[0] <= achievements < interval[1]
            )

            combo_rank = combo_conversion.get(fc, "")
            sync_rank = sync_conversion.get(fs, "")

            level_scores[level_index].append((diffs[level_index], achievements, score_rank, combo_rank, sync_rank))

    output_lines = []
    for level, scores in level_scores.items():
        if scores:
            output_lines.append(f"{diffs[level]} {music['level'][level]}")
            for score in scores:
                level, achievements, score_rank, combo_rank, sync_rank = score
                entry_output = f"{achievements} {score_rank}"
                if combo_rank and sync_rank:
                    entry_output += f" {combo_rank} {sync_rank}"
                elif combo_rank or sync_rank:
                    entry_output += f" {sync_rank}{sync_rank}"
                output_lines.append(entry_output)
        else:
            output_lines.append(f"{diffs[level]} {music['level'][level]}\n{msg.locale.t('maimai.message.info.no_record')}")

    return '\n'.join(output_lines)


async def get_level_process(message, payload, process, goal):
    song_played = []
    song_remain = []

    payload['version'] = list(set(version for version in plate_to_version.values()))
    res = await get_plate(msg, payload)
    verlist = res["verlist"]

    goal = goal.upper()
    if goal in score_to_rank.values():
        achievement = achievementList[list(score_to_rank.values()).index(goal) - 1]
        for song in verlist:
            if song['level'] == process and song['achievements'] < achievement:
                song_remain.append([song['id'], song['level_index']])
            song_played.append([song['id'], song['level_index']])
    elif goal in combo_conversion.values():
        combo_index = list(combo_conversion.values()).index(goal)
        for song in verlist:
            if song['level'] == process and ((song['fc'] and list(combo_conversion.keys()).index(song['fc']) < combo_index) or not song['fc']):
                song_remain.append([song['id'], song['level_index']])
            song_played.append([song['id'], song['level_index']])
    elif goal in sync_conversion.values():
        sync_index = list(sync_conversion.values()).index(goal)
        for song in verlist:
            if song['level'] == process and ((song['fs'] and list(sync_conversion.keys()).index(song['fs']) < sync_index) or not song['fs']):
                song_remain.append([song['id'], song['level_index']])
            song_played.append([song['id'], song['level_index']])

    for music in (await total_list.get()):
        for i, lv in enumerate(music.level[2:]):
            if lv == process and [int(music.id), i + 2] not in song_played:
                song_remain.append([int(music.id), i + 2])

    song_remain = sorted(song_remain, key=lambda i: int(i[1]))
    song_remain = sorted(song_remain, key=lambda i: int(i[0]))
    songs = []

    for song in song_remain:
        music = (await total_list.get()).by_id(str(song[0]))
        songs.append([music.id, music.title, diffs[song[1]], music.ds[song[1]], song[1], music.type])

    songs = sorted(songs, key=lambda s: int(s[0]))

    msg = ''
    if len(song_remain) > 0:
        if len(song_remain) < 50:
            song_record = [[s['id'], s['level_index']] for s in verlist]
            msg += f"{message.locale.t('maimai.message.process.level.last', process=process, goal=goal)}\n"
            for i, s in enumerate(sorted(songs, key=lambda i: i[3])):
                self_record = ''
                if [int(s[0]), s[-1]] in song_record:
                    record_index = song_record.index([int(s[0]), s[-1]])
                    if goal in score_to_rank.values():
                        self_record = str(verlist[record_index]['achievements']) + '%'
                    elif goal in combo_conversion.values():
                        if verlist[record_index]['fc']:
                            self_record = list(combo_conversion.values())[list(combo_conversion.keys()).index(verlist[record_index]['fc'])].upper()
                    elif goal in sync_conversion.values():
                        if verlist[record_index]['fs']:
                            self_record = list(sync_conversion.values())[list(sync_conversion.keys()).index(verlist[record_index]['fs'])].upper()
                msg += f"{s[0]}\u200B.{s[1]}{' (DX)' if s[5] == 'DX' else ''} {s[2]} {s[3]} {self_record}\n"
        else:
            msg = f"{message.locale.t('maimai.message.process.level.last', song_remain=len(song_remain), process=process, goal=goal)}"
    else:
        msg = f"{message.locale.t('maimai.message.process.level.completed', process=process, goal=goal)}"

    return msg
