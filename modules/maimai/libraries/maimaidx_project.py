from datetime import datetime

from core.utils.http import get_url
from .maimaidx_api_data import get_record, get_plate
from .maimaidx_music import TotalList

total_list = TotalList()

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

achievementList = [50.0, 60.0, 70.0, 75.0, 80.0, 90.0, 94.0, 97.0, 98.0, 99.0, 99.5, 100.0, 100.5]

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

    formatted_average_rating = "{:.4f}".format(average_rating)
    formatted_surpassing_rate = "{:.2f}".format(surpassing_rate)

    await msg.finish(msg.locale.t('maimai.message.rank', time=time, total_rank=total_rank, user=username,
                                  rating=rating, rank=rank, average_rating=formatted_average_rating,
                                  surpassing_rate=formatted_surpassing_rate))


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


async def get_level_process(msg, payload, process, goal):
    song_played = []
    song_remain = []

    scoreRank = list(score_to_rank.values())
    comboRank = list(combo_conversion.values())
    syncRank = list(sync_conversion.values())
    combo_rank = list(combo_conversion.keys())
    sync_rank = list(sync_conversion.keys())

    payload['version'] = list(set(version for version in plate_to_version.values()))
    res = await get_plate(msg, payload)
    verlist = res["verlist"]

    goal = goal.upper()
    if goal in scoreRank:
        achievement = achievementList[scoreRank.index(goal) - 1]
        for song in verlist:
            if song['level'] == process and song['achievements'] < achievement:
                song_remain.append([song['id'], song['level_index']])
            song_played.append([song['id'], song['level_index']])
    elif goal in comboRank:
        combo_index = comboRank.index(goal)
        for song in verlist:
            if song['level'] == process and ((song['fc'] and combo_rank.index(song['fc']) < combo_index) or not song['fc']):
                song_remain.append([song['id'], song['level_index']])
            song_played.append([song['id'], song['level_index']])
    elif goal in syncRank:
        sync_index = syncRank.index(goal)
        for song in verlist:
            if song['level'] == process and ((song['fs'] and sync_rank.index(song['fs']) < sync_index) or not song['fs']):
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

    output = ''
    if len(song_remain) > 0:
        if len(song_remain) < 50:
            song_record = [[s['id'], s['level_index']] for s in verlist]
            output += f"{msg.locale.t('maimai.message.process.level.last', process=process, goal=goal)}\n"
            for i, s in enumerate(sorted(songs, key=lambda i: i[3])):
                self_record = ''
                if [int(s[0]), s[-2]] in song_record:
                    record_index = song_record.index([int(s[0]), s[-2]])
                    if goal in scoreRank:
                        self_record = str(verlist[record_index]['achievements']) + '%'
                    elif goal in comboRank:
                        if verlist[record_index]['fc']:
                            self_record = comboRank[combo_rank.index(verlist[record_index]['fc'])]
                    elif goal in syncRank:
                        if verlist[record_index]['fs']:
                            self_record = syncRank[sync_rank.index(verlist[record_index]['fs'])]
                output += f"{s[0]}\u200B.{s[1]}{' (DX)' if s[5] == 'DX' else ''} {s[2]} {s[3]} {self_record}\n"
        else:
            output = f"{msg.locale.t('maimai.message.process.level', song_remain=len(song_remain), process=process, goal=goal)}"
    else:
        output = f"{msg.locale.t('maimai.message.process.level.completed', process=process, goal=goal)}"

    return output, len(song_remain)


async def get_score_list(msg, payload, level):
    song_list = []

    player_data = await get_record(msg, payload)
    username = player_data['username']

    payload['version'] = list(set(version for version in plate_to_version.values()))
    res = await get_plate(msg, payload)
    verlist = res["verlist"]
    music = (await total_list.get()).by_id(str(s['id']))

    for song in verlist:
        if song['level'] == level:
            song_list.append(song)
    output_lines = []
    for s in enumerate(sorted(song_list, key=lambda i: i['achievements'], reverse=True)):
        output = f"{music.id}\u200B.{music.title}{' (DX)' if music.type == 'DX' else ''} {diffs[s['level_index']]} {music.ds[s['level_index']]} {s['achievements']}%"
        if s["fc"] and s["fs"]:
            output += f" {combo_conversion.get(s['fc'], '')} {sync_conversion.get(s['fs'], '')}"
        elif s["fc"] or s["fs"]:
            output += f" {combo_conversion.get(s['fc'], '')}{sync_conversion.get(s['fs'], '')}"
        output_lines.append(output)

    outputs = '\n'.join(output_lines)

    res = f"{msg.locale.t('maimai.message.scorelist', user=username, level=level)}\n{outputs}"

    return res, len(output_lines)
