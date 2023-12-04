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
    '華': 'maimai でらっくす',
    '华': 'maimai でらっくす',
    '爽': 'maimai でらっくす Splash',
    '煌': 'maimai でらっくす Splash',
    '宙': 'maimai でらっくす UNiVERSE',
    '星': 'maimai でらっくす UNiVERSE',
    '祭': 'maimai でらっくす FESTiVAL',
    '祝': 'maimai でらっくす FESTiVAL'
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
    url = f"https://www.diving-fish.com/api/maimaidxprober/rating_ranking"
    rank_data = await get_url(url, 200, fmt='json')
    sorted_data = sorted(rank_data, key=lambda x: x['ra'], reverse=True)

    rating = 0
    rank = None
    total_rating = 0
    total_rank = len(sorted_data)

    for i, scoreboard in enumerate(sorted_data):
        if scoreboard['username'] == username:
            rank = i + 1
            rating = scoreboard['ra']
        total_rating += scoreboard['ra']

    if not rank:
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
                    entry_output += f" {combo_rank}{sync_rank}"
                output_lines.append(entry_output)
        else:
            output_lines.append(
                f"{diffs[level]} {music['level'][level]}\n{msg.locale.t('maimai.message.info.no_record')}")

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
            if song['level'] == process and (
                (song['fc'] and combo_rank.index(
                    song['fc']) < combo_index) or not song['fc']):
                song_remain.append([song['id'], song['level_index']])
            song_played.append([song['id'], song['level_index']])
    elif goal in syncRank:
        sync_index = syncRank.index(goal)
        for song in verlist:
            if song['level'] == process and (
                (song['fs'] and sync_rank.index(
                    song['fs']) < sync_index) or not song['fs']):
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
            output += f"{msg.locale.t('maimai.message.process.last', process=process, goal=goal)}\n"
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
                output += f"{s[0]}\u200B. {s[1]}{' (DX)' if s[5] == 'DX' else ''} {s[2]} {s[3]} {self_record}\n"
        else:
            output = f"{msg.locale.t('maimai.message.process', song_remain=len(song_remain), process=process, goal=goal)}"
    else:
        output = f"{msg.locale.t('maimai.message.process.completed', process=process, goal=goal)}"

    return output, len(song_remain)


async def get_score_list(msg, payload, level):
    song_list = []

    player_data = await get_record(msg, payload)
    username = player_data['username']

    payload['version'] = list(set(version for version in plate_to_version.values()))
    res = await get_plate(msg, payload)
    verlist = res["verlist"]

    for song in verlist:
        if song['level'] == level:
            song_list.append(song)
    output_lines = []
    for s in enumerate(sorted(song_list, key=lambda i: i['achievements'], reverse=True)):
        music = (await total_list.get()).by_id(str(s[1]['id']))
        output = f"{music.id}\u200B. {music.title}{' (DX)' if music.type == 'DX' else ''} {diffs[s[1]['level_index']]} {music.ds[s[1]['level_index']]} {s[1]['achievements']}%"
        if s[1]["fc"] and s[1]["fs"]:
            output += f" {combo_conversion.get(s[1]['fc'], '')} {sync_conversion.get(s[1]['fs'], '')}"
        elif s[1]["fc"] or s[1]["fs"]:
            output += f" {combo_conversion.get(s[1]['fc'], '')}{sync_conversion.get(s[1]['fs'], '')}"
        output_lines.append(output)

    outputs = '\n'.join(output_lines)

    res = f"{msg.locale.t('maimai.message.scorelist', user=username, level=level)}\n{outputs}"

    return res, len(output_lines)


async def get_plate_process(msg, payload, plate):
    song_played = []
    song_remain_basic = []
    song_remain_advanced = []
    song_remain_expert = []
    song_remain_master = []
    song_remain_remaster = []
    song_remain_difficult = []

    comboRank = list(combo_conversion.values())
    syncRank = list(sync_conversion.values())
    combo_rank = list(combo_conversion.keys())
    sync_rank = list(sync_conversion.keys())

    version = plate[0]
    goal = plate[1:]
    get_img = False

    if version == '真':
        payload['version'] = ['maimai', 'maimai PLUS']
    elif version in ['霸', '舞']:
        payload['version'] = list(set(version for version in list(plate_to_version.values())[:-9]))
    elif version in plate_to_version and version != '初':
        payload['version'] = [plate_to_version[version]]
    else:
        await msg.finish(msg.locale.t('maimai.message.plate.plate_not_found'))

    res = await get_plate(msg, payload)
    verlist = res["verlist"]

    if goal in ['将', '者']:
        for song in verlist:
            if song['level_index'] == 0 and song['achievements'] < (100.0 if goal == '将' else 80.0):
                song_remain_basic.append([song['id'], song['level_index']])
            if song['level_index'] == 1 and song['achievements'] < (100.0 if goal == '将' else 80.0):
                song_remain_advanced.append([song['id'], song['level_index']])
            if song['level_index'] == 2 and song['achievements'] < (100.0 if goal == '将' else 80.0):
                song_remain_expert.append([song['id'], song['level_index']])
            if song['level_index'] == 3 and song['achievements'] < (100.0 if goal == '将' else 80.0):
                song_remain_master.append([song['id'], song['level_index']])
            if version in [
                    '舞', '霸'] and song['level_index'] == 4 and song['achievements'] < (
                    100.0 if goal == '将' else 80.0):
                song_remain_remaster.append([song['id'], song['level_index']])
            song_played.append([song['id'], song['level_index']])
    elif goal in ['極', '极']:
        for song in verlist:
            if song['level_index'] == 0 and not song['fc']:
                song_remain_basic.append([song['id'], song['level_index']])
            if song['level_index'] == 1 and not song['fc']:
                song_remain_advanced.append([song['id'], song['level_index']])
            if song['level_index'] == 2 and not song['fc']:
                song_remain_expert.append([song['id'], song['level_index']])
            if song['level_index'] == 3 and not song['fc']:
                song_remain_master.append([song['id'], song['level_index']])
            if version == '舞' and song['level_index'] == 4 and not song['fc']:
                song_remain_remaster.append([song['id'], song['level_index']])
            song_played.append([song['id'], song['level_index']])
    elif goal == '舞舞':
        for song in verlist:
            if song['level_index'] == 0 and song['fs'] not in ['fsd', 'fsdp']:
                song_remain_basic.append([song['id'], song['level_index']])
            if song['level_index'] == 1 and song['fs'] not in ['fsd', 'fsdp']:
                song_remain_advanced.append([song['id'], song['level_index']])
            if song['level_index'] == 2 and song['fs'] not in ['fsd', 'fsdp']:
                song_remain_expert.append([song['id'], song['level_index']])
            if song['level_index'] == 3 and song['fs'] not in ['fsd', 'fsdp']:
                song_remain_master.append([song['id'], song['level_index']])
            if version == '舞' and song['level_index'] == 4 and song['fs'] not in ['fsd', 'fsdp']:
                song_remain_remaster.append([song['id'], song['level_index']])
            song_played.append([song['id'], song['level_index']])
    elif goal == '神':
        for song in verlist:
            if song['level_index'] == 0 and song['fc'] not in ['ap', 'app']:
                song_remain_basic.append([song['id'], song['level_index']])
            if song['level_index'] == 1 and song['fc'] not in ['ap', 'app']:
                song_remain_advanced.append([song['id'], song['level_index']])
            if song['level_index'] == 2 and song['fc'] not in ['ap', 'app']:
                song_remain_expert.append([song['id'], song['level_index']])
            if song['level_index'] == 3 and song['fc'] not in ['ap', 'app']:
                song_remain_master.append([song['id'], song['level_index']])
            if version == '舞' and song['level_index'] == 4 and song['fc'] not in ['ap', 'app']:
                song_remain_remaster.append([song['id'], song['level_index']])
            song_played.append([song['id'], song['level_index']])
    else:
        await msg.finish(msg.locale.t('maimai.message.plate.plate_not_found'))

    for music in (await total_list.get()):
        if music['basic_info']['from'] in payload['version']:
            if [int(music.id), 0] not in song_played:
                song_remain_basic.append([int(music.id), 0])
            if [int(music.id), 1] not in song_played:
                song_remain_advanced.append([int(music.id), 1])
            if [int(music.id), 2] not in song_played:
                song_remain_expert.append([int(music.id), 2])
            if [int(music.id), 3] not in song_played:
                song_remain_master.append([int(music.id), 3])
            if version in ['舞', '霸'] and len(music.level) == 5 and [int(music.id), 4] not in song_played:
                song_remain_remaster.append([int(music.id), 4])
    song_remain_basic = sorted(song_remain_basic, key=lambda i: int(i[0]))
    song_remain_advanced = sorted(song_remain_advanced, key=lambda i: int(i[0]))
    song_remain_expert = sorted(song_remain_expert, key=lambda i: int(i[0]))
    song_remain_master = sorted(song_remain_master, key=lambda i: int(i[0]))
    song_remain_remaster = sorted(song_remain_remaster, key=lambda i: int(i[0]))
    for song in song_remain_basic + song_remain_advanced + song_remain_expert + song_remain_master + song_remain_remaster:
        music = (await total_list.get()).by_id(str(song[0]))
        if music.ds[song[1]] > 13.6:
            song_remain_difficult.append([music.id, music.title, diffs[song[1]],
                                          music.ds[song[1]], song[1], music.type])

    prompt = msg.locale.t('maimai.message.plate', plate=plate,
                          song_remain_basic=len(song_remain_basic),
                          song_remain_advanced=len(song_remain_advanced),
                          song_remain_expert=len(song_remain_expert),
                          song_remain_master=len(song_remain_master))

    song_remain: list[list] = song_remain_basic + song_remain_advanced + \
        song_remain_expert + song_remain_master + song_remain_remaster
    song_record = [[s['id'], s['level_index']] for s in verlist]

    if version in ['舞', '霸']:
        prompt += msg.locale.t('maimai.message.plate.remaster', song_remain_remaster=len(song_remain_remaster))

    prompt += msg.locale.t('message.end')

    await msg.send_message(prompt.strip())

    output = ''
    if len(song_remain_difficult) > 0:
        if len(song_remain_difficult) < 50:
            output += msg.locale.t('maimai.message.plate.greater_13p.last') + '\n'
            for i, s in enumerate(sorted(song_remain_difficult, key=lambda i: i[3])):
                self_record = ''
                if [int(s[0]), s[-2]] in song_record:
                    record_index = song_record.index([int(s[0]), s[-2]])
                    if goal in ['将', '者']:
                        self_record = str(verlist[record_index]['achievements']) + '%'
                    elif goal in ['極', '极', '神']:
                        if verlist[record_index]['fc']:
                            self_record = comboRank[combo_rank.index(verlist[record_index]['fc'])]
                    elif goal == '舞舞':
                        if verlist[record_index]['fs']:
                            self_record = syncRank[sync_rank.index(verlist[record_index]['fs'])]
                output += f"{s[0]}\u200B. {s[1]}{' (DX)' if s[5] == 'DX' else ''} {s[2]} {s[3]} {self_record}".strip() + '\n'
            if len(song_remain_difficult) > 10:
                get_img = True
        else:
            output += msg.locale.t('maimai.message.plate.greater_13p', song_remain=len(song_remain_difficult))
    elif len(song_remain) > 0:
        for i, s in enumerate(song_remain):
            m = (await total_list.get()).by_id(str(s[0]))
            ds = m.ds[s[1]]
            song_remain[i].append(ds)
        if len(song_remain) < 50:
            output += msg.locale.t('maimai.message.plate.last') + '\n'
            for i, s in enumerate(sorted(song_remain, key=lambda i: i[2])):
                m = (await total_list.get()).by_id(str(s[0]))
                self_record = ''
                if [int(s[0]), s[-2]] in song_record:
                    record_index = song_record.index([int(s[0]), s[-2]])
                    if goal in ['将', '者']:
                        self_record = str(verlist[record_index]['achievements']) + '%'
                    elif goal in ['極', '极', '神']:
                        if verlist[record_index]['fc']:
                            self_record = comboRank[combo_rank.index(verlist[record_index]['fc'])]
                    elif goal == '舞舞':
                        if verlist[record_index]['fs']:
                            self_record = syncRank[sync_rank.index(verlist[record_index]['fs'])]
                output += f"{m.id}\u200B. {m.title}{' (DX)' if m.type == 'DX' else ''} {diffs[s[1]]} {m.ds[s[1]]} {self_record}".strip(
                ) + '\n'
            if len(song_remain) > 10:
                get_img = True
        else:
            output += msg.locale.t('maimai.message.plate.greater_13p.complete')
    else:
        output += msg.locale.t('maimai.message.plate.completed', plate=plate)

    return output, get_img
