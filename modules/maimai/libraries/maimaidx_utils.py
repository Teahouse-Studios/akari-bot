import math
import os
import random
from datetime import datetime

import ujson as json

from core.builtins import Bot, MessageChain, Plain
from core.utils.http import get_url
from core.utils.image import msgchain2image
from .maimaidx_apidata import get_record, get_total_record, get_plate
from .maimaidx_music import TotalList

SONGS_PER_PAGE = 30
SONGS_NEED_IMG = 10

assets_path = os.path.abspath('./assets/maimai')
total_list = TotalList()

sd_plate_conversion = {
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
    '辉': 'maimai FiNALE'
}

dx_plate_conversion = {
    '熊': 'maimai でらっくす',
    '華': 'maimai でらっくす',
    '华': 'maimai でらっくす',
    '爽': 'maimai でらっくす Splash',
    '煌': 'maimai でらっくす Splash',
    '宙': 'maimai でらっくす UNiVERSE',
    '星': 'maimai でらっくす UNiVERSE',
    '祭': 'maimai でらっくす FESTiVAL',
    '祝': 'maimai でらっくす FESTiVAL',
    '双': 'maimai でらっくす BUDDiES',
    '雙': 'maimai でらっくす BUDDiES',
}

grade_conversion = {
    '初段': 'grade1',
    '二段': 'grade2',
    '三段': 'grade3',
    '四段': 'grade4',
    '五段': 'grade5',
    '六段': 'grade6',
    '七段': 'grade7',
    '八段': 'grade8',
    '九段': 'grade9',
    '十段': 'grade10',
    '真初段': 'tgrade1',
    '真二段': 'tgrade2',
    '真三段': 'tgrade3',
    '真四段': 'tgrade4',
    '真五段': 'tgrade5',
    '真六段': 'tgrade6',
    '真七段': 'tgrade7',
    '真八段': 'tgrade8',
    '真九段': 'tgrade9',
    '真十段': 'tgrade10',
    '真皆伝': 'tgrade11',
    '真皆传': 'tgrade11',
    '真皆傳': 'tgrade11',
    '裏皆伝': 'tgrade12',
    '里皆传': 'tgrade12',
    '裡皆傳': 'tgrade12',
    '裏皆傳': 'tgrade12',
    'EXPERT初級': 'expert1',
    'EXPERT初级': 'expert1',
    'EXPERT中級': 'expert2',
    'EXPERT中级': 'expert2',
    'EXPERT上級': 'expert3',
    'EXPERT上级': 'expert3',
    'EXPERT超上級': 'expert4',
    'EXPERT超上級': 'expert4',
    'MASTER初級': 'master1',
    'MASTER初级': 'master1',
    'MASTER中級': 'master2',
    'MASTER中级': 'master2',
    'MASTER上級': 'master3',
    'MASTER上级': 'master3',
    'MASTER超上級': 'master4',
    'MASTER超上级': 'master4',
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
    "sync": "SYNC",
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

achievementList = [50.0, 60.0, 70.0, 75.0, 80.0, 90.0, 94.0, 97.0, 98.0, 99.0, 99.5, 100.0, 100.5]  # 各个成绩对应的评级分界线（向上取）
scoreRank = list(score_to_rank.values())  # Rank字典的值（文本显示）
comboRank = list(combo_conversion.values())  # Combo字典的值（文本显示）
syncRank = list(sync_conversion.values())  # Sync字典的值（文本显示）
combo_rank = list(combo_conversion.keys())  # Combo字典的键（API内显示）
sync_rank = list(sync_conversion.keys())  # Sync字典的键（API内显示）
plate_conversion = sd_plate_conversion | dx_plate_conversion


def get_diff(diff: str) -> int:
    diff_label = ['Basic', 'Advanced', 'Expert', 'Master', 'Re:MASTER']
    diff_label_abbr = ['bas', 'adv', 'exp', 'mas', 'rem']
    diff_label_zhs = ['绿', '黄', '红', '紫', '白']
    diff_label_zht = ['綠', '黃', '紅']

    diff = diff.lower()
    diff_label_lower = [label.lower() for label in diff_label]

    if diff in diff_label_zhs:
        level = diff_label_zhs.index(diff)
    elif diff in diff_label_zht:
        level = diff_label_zht.index(diff)
    elif diff in diff_label_abbr:
        level = diff_label_abbr.index(diff)
    elif diff in diff_label_lower:
        level = diff_label_lower.index(diff)
    else:
        level = None
    return level


def compute_rating(ds: float, achievement: float) -> int:
    achievement = round(achievement, 4)
    if achievement >= 100.5:
        base_ra = 22.4
    elif achievement == 100.4999:
        base_ra = 22.2
    elif achievement >= 100:
        base_ra = 21.6
    elif achievement == 99.9999:
        base_ra = 21.4
    elif achievement >= 99.5:
        base_ra = 21.1
    elif achievement >= 99:
        base_ra = 20.8
    elif achievement == 98.9999:
        base_ra = 20.6
    elif achievement >= 98:
        base_ra = 20.3
    elif achievement >= 97:
        base_ra = 20.0
    elif achievement == 96.9999:
        base_ra = 17.6
    elif achievement >= 94:
        base_ra = 16.8
    elif achievement >= 90:
        base_ra = 15.2
    elif achievement >= 80:
        base_ra = 13.6
    elif achievement == 79.9999:
        base_ra = 12.8
    elif achievement >= 75:
        base_ra = 12.0
    elif achievement >= 70:
        base_ra = 11.2
    elif achievement >= 60:
        base_ra = 9.6
    elif achievement >= 50:
        base_ra = 8.0
    elif achievement >= 40:
        base_ra = 6.4
    elif achievement >= 30:
        base_ra = 4.8
    elif achievement >= 20:
        base_ra = 3.2
    else:
        base_ra = 1.6
    return max(0, math.floor(ds * (min(100.5, achievement) / 100) * base_ra))


def calc_dxstar(dxscore: int, dxscore_max: int) -> str:
    percentage = (dxscore / dxscore_max) * 100
    stars = ""
    if 0.00 <= percentage < 85.00:
        stars = ""
    if 85.00 <= percentage < 90.00:
        stars = "✦"
    elif 90.00 <= percentage < 93.00:
        stars = "✦✦"
    elif 93.00 <= percentage < 95.00:
        stars = "✦✦✦"
    elif 95.00 <= percentage < 97.00:
        stars = "✦✦✦✦"
    else:
        stars = "✦✦✦✦✦"
    return stars


async def generate_best50_text(msg: Bot.MessageSession, payload: dict) -> MessageChain:
    data = await get_record(msg, payload)
    dx_charts = data["charts"]["dx"]
    sd_charts = data["charts"]["sd"]

    html = "<style>pre { font-size: 13px; }</style><div style='margin-left: 30px; margin-right: 20px;'>\n"
    html += f"{msg.locale.t('maimai.message.b50.text_prompt', user=data['username'], rating=data['rating'])}\n<pre>"
    html += f"Standard ({sum(chart['ra'] for chart in sd_charts)})\n"
    for idx, chart in enumerate(sd_charts, start=1):
        level = ''.join(filter(str.isalpha, chart["level_label"]))[:3].upper()
        music = (await total_list.get()).by_id(str(chart["song_id"]))
        dxscore_max = sum(music['charts'][chart['level_index']]['notes']) * 3
        dxstar = calc_dxstar(chart["dxScore"], dxscore_max)
        rank = next(
            # 根据成绩获得等级
            rank for interval, rank in score_to_rank.items() if interval[0] <= chart["achievements"] < interval[1]
        )
        title = chart["title"]
        title = title[:17] + '...' if len(title) > 20 else title
        line = "#{:<2} {:>5} {:<3} {:>8.4f}% {:<4} {:<3} {:<4} {:>4}->{:<3} {:<5} {:<20}\n".format(
            idx,
            chart["song_id"],
            level,
            chart["achievements"],
            rank,
            combo_conversion.get(chart["fc"], ""),
            sync_conversion.get(chart["fs"], ""),
            chart["ds"],
            chart["ra"],
            dxstar,
            title
        )
        html += line
    html += f"New ({sum(chart['ra'] for chart in dx_charts)})\n"
    for idx, chart in enumerate(dx_charts, start=1):
        level = ''.join(filter(str.isalpha, chart["level_label"]))[:3].upper()
        dxstar = calc_dxstar(chart["dxScore"], dxscore_max)
        rank = next(
            # 根据成绩获得等级
            rank for interval, rank in score_to_rank.items() if interval[0] <= chart["achievements"] < interval[1]
        )
        title = chart["title"]
        title = title[:17] + '...' if len(title) > 20 else title
        line = "#{:<2} {:>5} {:<3} {:>8.4f}% {:<4} {:<3} {:<4} {:>4}->{:<3} {:<5} {:<20}\n".format(
            idx,
            chart["song_id"],
            level,
            chart["achievements"],
            rank,
            combo_conversion.get(chart["fc"], ""),
            sync_conversion.get(chart["fs"], ""),
            chart["ds"],
            chart["ra"],
            dxstar,
            title
        )
        html += line
    html += "</pre>"
    time = msg.ts2strftime(datetime.now().timestamp(), iso=True, timezone=False)
    html += f"""<p style='font-size: 10px; text-align: right;'>Maimai Best50 Generator Beta\n{
        time}·Generated by Teahouse Studios \"Akaribot\"</p>"""
    html += "</div>"

    img = await msgchain2image([Plain(html)])
    if img:
        return img
    else:
        await msg.finish(msg.locale.t("error.config.webrender.invalid"))


async def get_rank(msg: Bot.MessageSession, payload: dict):
    time = msg.ts2strftime(datetime.now().timestamp(), timezone=False)

    url = f"https://www.diving-fish.com/api/maimaidxprober/rating_ranking"
    rank_data = await get_url(url, 200, fmt='json')
    rank_data = sorted(rank_data, key=lambda x: x['ra'], reverse=True)  # 根据rating排名并倒序

    player_data = await get_record(msg, payload)
    username = player_data['username']

    rating = 0
    rank = None
    total_rating = 0
    total_rank = len(rank_data)

    for i, scoreboard in enumerate(rank_data):
        if scoreboard['username'] == username:
            rank = i + 1
            rating = scoreboard['ra']
        total_rating += scoreboard['ra']

    if not rank:
        rank = total_rank

    average_rating = total_rating / total_rank
    surpassing_rate = (total_rank - rank) / total_rank * 100

    await msg.finish(msg.locale.t('maimai.message.rank',
                                  time=time,
                                  total_rank=total_rank,
                                  user=username,
                                  rating=rating,
                                  rank=rank,
                                  average_rating="{:.4f}".format(average_rating),
                                  surpassing_rate="{:.2f}".format(surpassing_rate)))


async def get_player_score(msg: Bot.MessageSession, payload: dict, input_id: str) -> str:
    res = await get_total_record(msg, payload, utage=True)  # 获取用户成绩信息
    verlist = res["verlist"]

    music = (await total_list.get()).by_id(input_id)
    level_scores = {level: [] for level in range(len(music['level']))}  # 获取歌曲难度列表

    for entry in verlist:
        sid = entry["id"]
        achievements = entry["achievements"]
        fc = entry["fc"]
        fs = entry["fs"]
        level_index = entry["level_index"]

        if str(sid) == input_id:
            score_rank = next(
                # 根据成绩获得等级
                rank for interval, rank in score_to_rank.items() if interval[0] <= achievements < interval[1]
            )

            combo_rank = combo_conversion.get(fc, "")  # Combo字典转换
            sync_rank = sync_conversion.get(fs, "")  # Sync字典转换

            level_scores[level_index].append((diffs[level_index], achievements, score_rank, combo_rank, sync_rank))

    output_lines = []
    for level, scores in level_scores.items():  # 使用循环输出格式化文本
        if scores:
            output_lines.append(f"{diffs[level]} {music['level'][level]}")  # 难度字典转换
            for score in scores:
                level, achievements, score_rank, combo_rank, sync_rank = score
                entry_output = f"{achievements:.4f} {score_rank}"
                if combo_rank and sync_rank:
                    entry_output += f" {combo_rank} {sync_rank}"
                elif combo_rank or sync_rank:
                    entry_output += f" {combo_rank}{sync_rank}"
                output_lines.append(entry_output)
        else:
            output_lines.append(
                f"{diffs[level]} {music['level'][level]}\n{msg.locale.t('maimai.message.info.no_record')}")

    return '\n'.join(output_lines)


async def get_level_process(msg: Bot.MessageSession, payload: dict, process: str, goal: str) -> tuple[str, bool]:
    song_played = []
    song_remain = []

    res = await get_total_record(msg, payload)  # 获取用户成绩信息
    verlist = res["verlist"]

    goal = goal.upper()  # 输入强制转换为大写以适配字典
    if goal in scoreRank:
        achievement = achievementList[scoreRank.index(goal) - 1]  # 根据列表将输入评级转换为成绩分界线
        for song in verlist:
            if song['level'] == process and song['achievements'] < achievement:  # 达成难度条件但未达成目标条件
                song_remain.append([song['id'], song['level_index']])  # 将剩余歌曲ID和难度加入目标列表
            song_played.append([song['id'], song['level_index']])  # 将已游玩歌曲ID和难度加入列表
    elif goal in comboRank:
        combo_index = comboRank.index(goal)  # 根据API结果字典转换
        for song in verlist:
            if song['level'] == process and (
                (song['fc'] and combo_rank.index(
                    song['fc']) < combo_index) or not song['fc']):  # 达成难度条件但未达成目标条件
                song_remain.append([song['id'], song['level_index']])  # 将剩余歌曲ID和难度加入目标列表
            song_played.append([song['id'], song['level_index']])  # 将已游玩歌曲ID和难度加入列表
    elif goal in syncRank:
        sync_index = syncRank.index(goal)  # 根据API结果字典转换
        for song in verlist:
            if song['level'] == process and (
                (song['fs'] and sync_rank.index(
                    song['fs']) < sync_index) or not song['fs']):  # 达成难度条件但未达成目标条件
                song_remain.append([song['id'], song['level_index']])  # 将剩余歌曲ID和难度加入目标列表
            song_played.append([song['id'], song['level_index']])  # 将已游玩歌曲ID和难度加入列表
    for music in (await total_list.get()):  # 遍历歌曲列表
        for i, lv in enumerate(music.level[2:]):
            if lv == process and [int(music.id), i + 2] not in song_played:
                song_remain.append([int(music.id), i + 2])  # 将未游玩歌曲ID和难度加入目标列表

    song_remain = sorted(song_remain, key=lambda i: int(i[1]))  # 根据难度排序结果
    song_remain = sorted(song_remain, key=lambda i: int(i[0]))  # 根据ID排序结果

    songs = []
    for song in song_remain:  # 循环查询歌曲信息
        music = (await total_list.get()).by_id(str(song[0]))
        songs.append([music.id, music.title, diffs[song[1]], music.ds[song[1]], song[1], music.type])

    output = ''
    get_img = False
    if len(song_remain) > 0:
        song_record = [[s['id'], s['level_index']] for s in verlist]
        output += f"{msg.locale.t('maimai.message.process.last', process=process, goal=goal)}\n"
        for i, s in enumerate(sorted(songs, key=lambda i: i[3], reverse=True)):  # 显示剩余歌曲信息
            self_record = ''
            if [int(s[0]), s[-2]] in song_record:
                record_index = song_record.index([int(s[0]), s[-2]])
                if goal in scoreRank:
                    self_record = str("{:.4f}".format(verlist[record_index]['achievements'])) + '%'
                elif goal in comboRank:
                    if verlist[record_index]['fc']:
                        self_record = comboRank[combo_rank.index(verlist[record_index]['fc'])]
                elif goal in syncRank:
                    if verlist[record_index]['fs']:
                        self_record = syncRank[sync_rank.index(verlist[record_index]['fs'])]
            output += f"{s[0]}\u200B. {s[1]}{' (DX)' if s[5] == 'DX' else ''} {s[2]} {s[3]} {self_record}\n"
            if i == SONGS_PER_PAGE - 1:
                break
        if len(song_remain) > SONGS_PER_PAGE:
            output += msg.locale.t('maimai.message.process', song_remain=len(song_remain), process=process, goal=goal)
        if len(song_remain) > SONGS_NEED_IMG:
            get_img = True
    else:
        await msg.finish(msg.locale.t('maimai.message.process.completed', process=process, goal=goal))

    return output, get_img


async def get_score_list(msg: Bot.MessageSession, payload: dict, level: str, page: str) -> tuple[str, bool]:
    player_data = await get_record(msg, payload)

    res = await get_total_record(msg, payload)  # 获取用户成绩信息
    verlist = res["verlist"]

    song_list = []
    for song in verlist:
        if song['level'] == level:
            song_list.append(song)  # 将符合难度的成绩加入列表

    output_lines = []
    total_pages = (len(song_list) + SONGS_PER_PAGE - 1) // SONGS_PER_PAGE
    page = max(min(int(page), total_pages), 1) if page.isdigit() else 1
    for i, s in enumerate(sorted(song_list, key=lambda i: i['achievements'], reverse=True)):  # 根据成绩排序
        if (page - 1) * SONGS_PER_PAGE <= i < page * SONGS_PER_PAGE:
            music = (await total_list.get()).by_id(str(s['id']))
            output = f"{music.id}\u200B. {music.title}{' (DX)' if music.type == 'DX' else ''} {diffs[s['level_index']]} {
                music.ds[s['level_index']]} {s['achievements']:.4f}%"
            if s["fc"] and s["fs"]:
                output += f" {combo_conversion.get(s['fc'], '')} {sync_conversion.get(s['fs'], '')}"
            elif s["fc"] or s["fs"]:
                output += f" {combo_conversion.get(s['fc'], '')}{sync_conversion.get(s['fs'], '')}"
            output_lines.append(output)

    outputs = '\n'.join(output_lines)
    res = f"{msg.locale.t('maimai.message.scorelist', user=player_data['username'], level=level)}\n{outputs}"
    get_img = False

    if len(output_lines) == 0:
        await msg.finish(msg.locale.t("maimai.message.chart_not_found"))
    elif len(output_lines) > 10:
        res += f"\n{msg.locale.t('maimai.message.pages', page=page, total_pages=total_pages)}"
        get_img = True

    return res, get_img


async def get_plate_process(msg: Bot.MessageSession, payload: dict, plate: str) -> tuple[str, bool]:
    song_played = []
    song_remain_basic = []
    song_remain_advanced = []
    song_remain_expert = []
    song_remain_master = []
    song_remain_remaster = []
    song_remain_difficult = []

    version_mapping = {'霸': '覇', '晓': '暁', '樱': '櫻', '堇': '菫', '辉': '輝', '华': '華', '雙': '双'}
    goal_mapping = {'将': '將', '极': '極'}

    version = plate[0]
    goal = plate[1:]
    get_img = False

    if version in version_mapping:
        version = version_mapping[version]
    if goal in goal_mapping:
        goal = goal_mapping[goal]
    plate = version + goal

    if version == '真':  # 真代为无印版本
        payload['version'] = ['maimai', 'maimai PLUS']
    elif version in ['覇', '舞']:  # 霸者和舞牌需要全版本
        payload['version'] = list(set(ver for ver in list(sd_plate_conversion.values())))
    elif version in plate_conversion and version != '初':  # “初”不是版本名称
        payload['version'] = [plate_conversion[version]]
    else:
        await msg.finish(msg.locale.t('maimai.message.plate.plate_not_found'))

    res = await get_plate(msg, payload, version)  # 获取用户成绩信息
    verlist = res["verlist"]

    if goal in ['將', '者']:
        for song in verlist:  # 将剩余歌曲ID和难度加入目标列表
            if song['level_index'] == 0 and song['achievements'] < (100.0 if goal == '將' else 80.0):
                song_remain_basic.append([song['id'], song['level_index']])
            if song['level_index'] == 1 and song['achievements'] < (100.0 if goal == '將' else 80.0):
                song_remain_advanced.append([song['id'], song['level_index']])
            if song['level_index'] == 2 and song['achievements'] < (100.0 if goal == '將' else 80.0):
                song_remain_expert.append([song['id'], song['level_index']])
            if song['level_index'] == 3 and song['achievements'] < (100.0 if goal == '將' else 80.0):
                song_remain_master.append([song['id'], song['level_index']])
            if version in ['舞', '覇'] and song['level_index'] == 4 and song['achievements'] < (
                    100.0 if goal == '將' else 80.0):
                song_remain_remaster.append([song['id'], song['level_index']])  # 霸者和舞牌需要Re:MASTER难度
            song_played.append([song['id'], song['level_index']])
    elif goal == '極':
        for song in verlist:  # 将剩余歌曲ID和难度加入目标列表
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
        for song in verlist:  # 将剩余歌曲ID和难度加入目标列表
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
        for song in verlist:  # 将剩余歌曲ID和难度加入目标列表
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

    for music in (await total_list.get()):  # 将未游玩歌曲ID加入目标列表
        if music['basic_info']['from'] in payload['version'] and int(music.id) < 100000:  # 过滤宴谱
            if [int(music.id), 0] not in song_played:
                song_remain_basic.append([int(music.id), 0])
            if [int(music.id), 1] not in song_played:
                song_remain_advanced.append([int(music.id), 1])
            if [int(music.id), 2] not in song_played:
                song_remain_expert.append([int(music.id), 2])
            if [int(music.id), 3] not in song_played:
                song_remain_master.append([int(music.id), 3])
            if version in ['舞', '覇'] and len(music.level) == 5 and [int(music.id), 4] not in song_played:
                song_remain_remaster.append([int(music.id), 4])
    song_remain_basic = sorted(song_remain_basic, key=lambda i: int(i[0]))  # 根据ID排序结果
    song_remain_advanced = sorted(song_remain_advanced, key=lambda i: int(i[0]))
    song_remain_expert = sorted(song_remain_expert, key=lambda i: int(i[0]))
    song_remain_master = sorted(song_remain_master, key=lambda i: int(i[0]))
    song_remain_remaster = sorted(song_remain_remaster, key=lambda i: int(i[0]))
    for song in song_remain_basic + song_remain_advanced + \
            song_remain_expert + song_remain_master + song_remain_remaster:  # 循环查询歌曲信息
        music = (await total_list.get()).by_id(str(song[0]))
        if music.ds[song[1]] > 13.6:  # 将难度为13+以上的谱面加入列表
            song_remain_difficult.append([music.id, music.title, diffs[song[1]],
                                          music.ds[song[1]], song[1], music.type])

    if version == '真':
        song_expect = [70]
    elif version == '檄':
        song_expect = [341]
    elif version == '桃':
        song_expect = [451, 455, 460]
    elif version == '菫':
        song_expect = [853]
    elif version == '輝':
        song_expect = [792]
    elif version == '舞':
        song_expect = [341, 451, 455, 460, 792, 853]
    else:
        song_expect = []

    song_remain_basic = [music for music in song_remain_basic if music[0] not in song_expect]
    song_remain_advanced = [music for music in song_remain_advanced if music[0] not in song_expect]
    song_remain_expert = [music for music in song_remain_expert if music[0] not in song_expect]
    song_remain_master = [music for music in song_remain_master if music[0] not in song_expect]
    song_remain_remaster = [music for music in song_remain_remaster if music[0] not in song_expect]
    song_remain_difficult = [music for music in song_remain_difficult if int(music[0]) not in song_expect]
    song_remain: list[list] = song_remain_basic + song_remain_advanced + \
        song_remain_expert + song_remain_master + song_remain_remaster

    prompt = [msg.locale.t('maimai.message.plate.prompt', plate=plate)]
    if song_remain_basic:
        prompt.append(msg.locale.t('maimai.message.plate.basic', song_remain=len(song_remain_basic)))
    if song_remain_advanced:
        prompt.append(msg.locale.t('maimai.message.plate.advanced', song_remain=len(song_remain_advanced)))
    if song_remain_expert:
        prompt.append(msg.locale.t('maimai.message.plate.expert', song_remain=len(song_remain_expert)))
    if song_remain_master:
        prompt.append(msg.locale.t('maimai.message.plate.master', song_remain=len(song_remain_master)))
    if version in ['舞', '覇'] and song_remain_remaster:  # 霸者和舞牌需要Re:MASTER难度
        prompt.append(msg.locale.t('maimai.message.plate.remaster', song_remain=len(song_remain_remaster)))

    if song_remain:
        await msg.send_message('\n'.join(prompt))

    song_record = [[s['id'], s['level_index']] for s in verlist]

    output = ''
    if len(song_remain_difficult) > 0:
        if len(song_remain_difficult) < SONGS_PER_PAGE:
            output += msg.locale.t('maimai.message.plate.difficult.last') + '\n'
            for i, s in enumerate(sorted(song_remain_difficult, key=lambda i: i[3])):  # 根据定数排序结果
                self_record = ''
                if [int(s[0]), s[-2]] in song_record:  # 显示剩余13+以上歌曲信息
                    record_index = song_record.index([int(s[0]), s[-2]])
                    if goal in ['將', '者']:
                        self_record = f"{str('{:.4f}'.format(verlist[record_index]['achievements']))}%"
                    elif goal in ['極', '神']:
                        if verlist[record_index]['fc']:
                            self_record = comboRank[combo_rank.index(verlist[record_index]['fc'])]
                    elif goal == '舞舞':
                        if verlist[record_index]['fs']:
                            self_record = syncRank[sync_rank.index(verlist[record_index]['fs'])]
                output += f"{s[0]}\u200B. {s[1]}{' (DX)' if s[5] == 'DX' else ''} {s[2]
                                                                                   } {s[3]} {self_record}".strip() + '\n'
            if len(song_remain_difficult) > SONGS_NEED_IMG:
                get_img = True
        else:
            output += msg.locale.t('maimai.message.plate.difficult', song_remain=len(song_remain_difficult))
    elif len(song_remain) > 0:
        for i, s in enumerate(song_remain):
            m = (await total_list.get()).by_id(str(s[0]))
            ds = m.ds[s[1]]
            song_remain[i].append(ds)
        if len(song_remain) < SONGS_PER_PAGE:
            output += msg.locale.t('maimai.message.plate.last') + '\n'
            for i, s in enumerate(sorted(song_remain, key=lambda i: i[2])):  # 根据难度排序结果
                m = (await total_list.get()).by_id(str(s[0]))
                self_record = ''
                if [int(s[0]), s[-2]] in song_record:  # 显示剩余歌曲信息
                    record_index = song_record.index([int(s[0]), s[-2]])
                    if goal in ['將', '者']:
                        self_record = str("{:.4f}".format(verlist[record_index]['achievements'])) + '%'
                    elif goal in ['極', '神']:
                        if verlist[record_index]['fc']:
                            self_record = comboRank[combo_rank.index(verlist[record_index]['fc'])]
                    elif goal == '舞舞':
                        if verlist[record_index]['fs']:
                            self_record = syncRank[sync_rank.index(verlist[record_index]['fs'])]
                output += f"{m.id}\u200B. {m.title}{' (DX)' if m.type ==
                                                    'DX' else ''} {diffs[s[1]]} {m.ds[s[1]]} {self_record}".strip() + '\n'
            if len(song_remain) > SONGS_NEED_IMG:
                get_img = True
        else:
            output += msg.locale.t('maimai.message.plate.difficult.completed')
    else:
        output += msg.locale.t('maimai.message.plate.completed', plate=plate)

    return output, get_img


async def get_grade_info(msg: Bot.MessageSession, grade: str):
    file_path = os.path.join(assets_path, "mai_grade_info.json")
    with open(file_path, 'r') as file:
        data = json.load(file)

    def key_process(input_key, conv_dict):
        key = next((k for k, v in conv_dict.items() if input_key == k), None)
        if key is not None:
            value = conv_dict[key]
            new_key = next((k for k, v in conv_dict.items() if v == value), None)
            return value, new_key
        else:
            return None, input_key

    grade = grade.upper()  # 输入强制转换为大写以适配字典
    grade_key, grade = key_process(grade, grade_conversion)

    if not grade_key:
        await msg.finish(msg.locale.t('maimai.message.grade.grade_not_found'))
    elif grade_key.startswith('tgrade'):
        grade_type = 'tgrade'
    elif grade_key.startswith('grade'):
        grade_type = 'grade'
    else:
        grade_type = 'rgrade'

    chart_info = []
    grade_data = data[grade_type][grade_key]
    condition = grade_data["condition"]
    if grade_type != 'rgrade':
        charts = grade_data["charts"]

        for chart in charts:
            music = (await total_list.get()).by_id(str(chart['song_id']))
            level = chart['level_index']
            chart_info.append(
                f"{
                    music['id']}\u200B. {
                    music['title']}{
                    ' (DX)' if music['type'] == 'DX' else ''} {
                    diffs[level]} {
                        music['level'][level]}")

    else:
        base = grade_data["base"]
        if 'master' in grade_key:
            music_data_master = (await total_list.get()).filter(ds=(base[0], base[1]), diff=[3])
            music_data_remaster = (await total_list.get()).filter(ds=(base[0], base[1]), diff=[4])
            music_data = music_data_master + music_data_remaster

            for i in range(4):
                music = random.choice(music_data)
                if music in music_data_master and music in music_data_remaster:
                    level = random.choice([3, 4])
                elif music in music_data_remaster:
                    level = 4
                else:
                    level = 3
                chart_info.append(
                    f"{
                        music['id']}\u200B. {
                        music['title']}{
                        ' (DX)' if music['type'] == 'DX' else ''} {
                        diffs[level]} {
                        music['level'][level]}")
        else:
            level = 2
            music_data = (await total_list.get()).filter(ds=(base[0], base[1]), diff=[level])
            for i in range(4):
                music = music_data.random()
                chart_info.append(
                    f"{
                        music['id']}\u200B. {
                        music['title']}{
                        ' (DX)' if music['type'] == 'DX' else ''} {
                        diffs[level]} {
                        music['level'][level]}")

    content = '\n'.join(chart_info)
    condition_info = f"GREAT{condition[0]}/GOOD{condition[1]}/MISS{condition[2]}/CLEAR{condition[3]}"

    await msg.finish(msg.locale.t('maimai.message.grade', grade=grade, content=content, life=grade_data["life"], condition=condition_info))