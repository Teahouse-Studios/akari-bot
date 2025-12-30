import math
import time

import orjson

from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import I18NContext, Plain
from core.utils.http import get_url
from core.utils.random import Random
from .maimaidx_apidata import get_record, get_song_record, get_total_record, get_plate
from .maimaidx_mapping import *
from .maimaidx_music import TotalList
from ..database.models import DivingProberBindInfo

total_list = TotalList()


async def get_diving_prober_bind_info(msg: Bot.MessageSession):
    bind_info = await DivingProberBindInfo.get_by_sender_id(msg, create=False)
    if not bind_info:
        if msg.session_info.sender_from == "QQ":
            payload = {"qq": msg.session_info.get_common_sender_id(), "b50": True}
        else:
            await msg.finish(I18NContext("maimai.message.user_unbound", prefix=msg.session_info.prefixes[0]))
    else:
        payload = {"username": bind_info.username, "b50": True}
    return payload


def get_diff(diff: str) -> int:
    diff = diff.lower()
    diff_list_lower = [label.lower() for label in diff_list]

    if diff in diff_list_lower:
        level = diff_list_lower.index(diff)
    elif diff in diff_list_abbr:
        level = diff_list_abbr.index(diff)
    elif diff in diff_list_zh:
        level = diff_list_zh.index(diff)
    elif diff in diff_list_zhs:
        level = diff_list_zhs.index(diff)
    elif diff in diff_list_zht:
        level = diff_list_zht.index(diff)
    else:
        level = 0
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
    percentage = round((dxscore / dxscore_max) * 100, 2)
    stars = ""
    if 0.00 <= percentage < 85.00:
        stars = ""
    elif 85.00 <= percentage < 90.00:
        stars = "✦"
    elif 90.00 <= percentage < 93.00:
        stars = "✦✦"
    elif 93.00 <= percentage < 95.00:
        stars = "✦✦✦"
    elif 95.00 <= percentage < 97.00:
        stars = "✦✦✦✦"
    elif percentage >= 97.00:
        stars = "✦✦✦✦✦"
    return stars


async def get_rank(msg: Bot.MessageSession, payload: dict, use_cache: bool = True):
    time_ = msg.format_time(time.time(), timezone=False)

    url = "https://www.diving-fish.com/api/maimaidxprober/rating_ranking"
    rank_data = await get_url(url, 200, fmt="json")
    rank_data = sorted(rank_data, key=lambda x: x["ra"], reverse=True)  # 根据rating排名并倒序

    player_data: dict = await get_record(msg, payload, use_cache)
    username = player_data["username"]

    rating = 0
    rank = None
    total_rating = 0
    total_rank = len(rank_data)

    # 记录上一个ra的值和排名
    previous_ra = None
    previous_rank = None

    for i, scoreboard in enumerate(rank_data):
        if scoreboard["ra"] != previous_ra:
            current_rank = i + 1
            previous_rank = current_rank
        elif scoreboard["ra"] == previous_ra:
            current_rank = previous_rank

        if scoreboard["username"] == username:
            rank = current_rank
            rating = scoreboard["ra"]

        total_rating += scoreboard["ra"]
        previous_ra = scoreboard["ra"]

    if not rank:
        rank = total_rank

    average_rating = total_rating / total_rank
    surpassing_rate = (total_rank - rank) / total_rank * 100

    await msg.finish(I18NContext("maimai.message.rank",
                                 time=time_,
                                 total_rank=total_rank,
                                 user=username,
                                 rating=rating,
                                 rank=rank,
                                 average_rating=f"{average_rating:.4f}",
                                 surpassing_rate=f"{surpassing_rate:.2f}"))


async def get_player_score(msg: Bot.MessageSession, payload: dict, input_id: str,
                           use_cache: bool = True) -> MessageChain:
    music = (await total_list.get()).by_id(input_id)
    level_scores = {level: [] for level in range(len(music["level"]))}  # 获取歌曲难度列表

    try:
        res: dict = await get_song_record(msg, payload, input_id, use_cache)
        for sid, records in res.items():
            if str(sid) == input_id:
                for entry in records:
                    achievements = entry["achievements"]
                    fc = entry["fc"]
                    fs = entry["fs"]
                    level_index = entry["level_index"]
                    try:
                        score_rank = next(
                            # 根据成绩获得等级
                            rank for interval, rank in score_to_rate.items() if
                            interval[0] <= achievements < interval[1]
                        )
                    except StopIteration:
                        continue
                    combo_rank = combo_mapping.get(fc, "")  # Combo字典转换
                    sync_rank = sync_mapping.get(fs, "")  # Sync字典转换
                    dxscore = entry.get("dxScore", 0)
                    dxscore_max = sum(music["charts"][level_index]["notes"]) * 3
                    level_scores[level_index].append(
                        (diffs[level_index], achievements, score_rank, combo_rank, sync_rank, dxscore, dxscore_max)
                    )
    except Exception:
        res = await get_total_record(msg, payload, True, use_cache)
        records = res["verlist"]

        for entry in records:
            if str(entry.get("id")) == input_id:
                achievements = entry["achievements"]
                fc = entry["fc"]
                fs = entry["fs"]
                level_index = entry["level_index"]
                try:
                    score_rank = next(
                        # 根据成绩获得等级
                        rank for interval, rank in score_to_rate.items() if interval[0] <= achievements < interval[1]
                    )
                except StopIteration:
                    continue
                combo_rank = combo_mapping.get(fc, "")  # Combo字典转换
                sync_rank = sync_mapping.get(fs, "")  # Sync字典转换
                level_scores[level_index].append((diffs[level_index], achievements, score_rank, combo_rank, sync_rank))

    msg_chain = MessageChain.assign()
    if int(input_id) >= 100000:
        if len(level_scores.items()) > 1:
            await msg.finish(I18NContext("maimai.message.score.utage"))
        else:
            for level, scores in level_scores.items():  # 使用循环输出格式化文本
                msg_chain.append(Plain(f"U·TA·GE {music["level"][level]}"))  # 难度字典转换
                if scores:
                    for score in scores:
                        level, achievements, score_rank, combo_rank, sync_rank, *dx = score
                        entry_output = f"{achievements:.4f} {score_rank}"
                        if combo_rank and sync_rank:
                            entry_output += f" {combo_rank} {sync_rank}"
                        elif combo_rank or sync_rank:
                            entry_output += f" {combo_rank}{sync_rank}"
                        if dx and dx[0]:
                            entry_output += f"\n{dx[0]}/{dx[1]} {calc_dxstar(dx[0], dx[1])}"
                        msg_chain.append(Plain(entry_output))
                else:
                    msg_chain.append(I18NContext("maimai.message.score.no_record"))
    else:
        for level, scores in level_scores.items():  # 使用循环输出格式化文本
            msg_chain.append(Plain(f"{diffs[level]} {music["level"][level]}"))
            if scores:  # 难度字典转换
                for score in scores:
                    level, achievements, score_rank, combo_rank, sync_rank, *dx = score
                    entry_output = f"{achievements:.4f} {score_rank}"
                    if combo_rank and sync_rank:
                        entry_output += f" {combo_rank} {sync_rank}"
                    elif combo_rank or sync_rank:
                        entry_output += f" {combo_rank}{sync_rank}"
                    if dx and dx[0]:
                        entry_output += f"\n{dx[0]}/{dx[1]} {calc_dxstar(dx[0], dx[1])}"
                    msg_chain.append(Plain(entry_output))
            else:
                msg_chain.append(I18NContext("maimai.message.score.no_record"))

    return msg_chain


async def get_score_list(msg: Bot.MessageSession, payload: dict, level: str, page: int,
                         use_cache: bool = True) -> tuple[MessageChain, bool]:
    res: dict = await get_total_record(msg, payload, use_cache=use_cache)
    records = res["verlist"]

    player_data: dict = await get_record(msg, payload, use_cache)
    song_list = []
    for song in records:
        if song["level"] == level:
            song_list.append(song)  # 将符合难度的成绩加入列表

    output_line = []
    total_pages = (len(song_list) + SONGS_PER_PAGE - 1) // SONGS_PER_PAGE
    page = max(min(int(page), total_pages), 1)
    for i, s in enumerate(sorted(song_list, key=lambda i: i["achievements"], reverse=True)):  # 根据成绩排序
        if (page - 1) * SONGS_PER_PAGE <= i < page * SONGS_PER_PAGE:
            music = (await total_list.get()).by_id(str(s["id"]))

            output = f"{music.id} - {music.title}{" (DX)" if music.type == "DX" else ""} [{diffs[s["level_index"]]}] {
                music.ds[s["level_index"]]} {s["achievements"]:.4f}%"
            if s["fc"] and s["fs"]:
                output += f" {combo_mapping.get(s["fc"], "")} {sync_mapping.get(s["fs"], "")}"
            elif s["fc"] or s["fs"]:
                output += f" {combo_mapping.get(s["fc"], "")}{sync_mapping.get(s["fs"], "")}"
            output_line.append(Plain(output))

    msg_chain = MessageChain.assign(
        I18NContext(
            "maimai.message.scorelist",
            user=player_data["username"],
            level=level)) + output_line
    get_img = False

    if len(output_line) == 0:
        await msg.finish(I18NContext("maimai.message.chart_not_found"))
    elif len(output_line) > 10:
        msg_chain.append(I18NContext("maimai.message.pages", page=page, total_pages=total_pages))
        get_img = True

    return msg_chain, get_img


async def get_level_process(msg: Bot.MessageSession, payload: dict, level: str, goal: str,
                            use_cache: bool = True) -> tuple[MessageChain, bool]:
    song_played = []
    song_remain = []

    res: dict = await get_total_record(msg, payload, use_cache=use_cache)
    verlist = res["verlist"]

    goal = goal.upper()  # 输入强制转换为大写以适配字典
    if goal in rate_list:
        achievement = achievement_list[rate_list.index(goal) - 1]  # 根据列表将输入评级转换为成绩分界线
        for song in verlist:
            if song["level"] == level and song["achievements"] < achievement:  # 达成难度条件但未达成目标条件
                song_remain.append((str(song["id"]), song["level_index"]))  # 将剩余歌曲ID和难度加入目标列表
            song_played.append((str(song["id"]), song["level_index"]))  # 将已游玩歌曲ID和难度加入列表
    elif goal in combo_list:
        combo_index = combo_list.index(goal)  # 根据API结果字典转换
        for song in verlist:
            if song["level"] == level and (
                (song["fc"] and combo_list_raw.index(
                    song["fc"]) < combo_index) or not song["fc"]):  # 达成难度条件但未达成目标条件
                song_remain.append((str(song["id"]), song["level_index"]))  # 将剩余歌曲ID和难度加入目标列表
            song_played.append((str(song["id"]), song["level_index"]))  # 将已游玩歌曲ID和难度加入列表
    elif goal in sync_list:
        sync_index = sync_list.index(goal)  # 根据API结果字典转换
        for song in verlist:
            if song["level"] == level and (
                (song["fs"] and sync_list_raw.index(
                    song["fs"]) < sync_index) or not song["fs"]):  # 达成难度条件但未达成目标条件
                song_remain.append((str(song["id"]), song["level_index"]))  # 将剩余歌曲ID和难度加入目标列表
            song_played.append((str(song["id"]), song["level_index"]))  # 将已游玩歌曲ID和难度加入列表

    for music in ((await total_list.get()).filter(level=level)):  # 遍历歌曲列表
        for i in enumerate(music.level):
            if i[1] == level and int(music.id) < 100000 and (music.id, i[0]) not in song_played:
                song_remain.append((music.id, i[0]))  # 将未游玩歌曲ID和难度加入目标列表

    song_remain = sorted(song_remain, key=lambda i: int(i[1]))  # 根据难度排序结果
    song_remain = sorted(song_remain, key=lambda i: int(i[0]))  # 根据ID排序结果

    song_detail = []
    for song in song_remain:  # 循环查询歌曲信息
        music = (await total_list.get()).by_id(song[0])
        song_detail.append((music.id, music.title, diffs[song[1]], music.ds[song[1]], song[1], music.type))

    msg_chain = MessageChain.assign()
    get_img = False
    if len(song_remain) > 0:
        song_record = [(str(s["id"]), s["level_index"]) for s in verlist]
        msg_chain.append(I18NContext("maimai.message.process.last", level=level, goal=goal))
        for i, s in enumerate(sorted(song_detail, key=lambda i: i[3], reverse=True)):  # 显示剩余歌曲信息
            self_record = ""
            if (s[0], s[-2]) in song_record:
                record_index = song_record.index((s[0], s[-2]))
                if goal in rate_list:
                    self_record = f"{verlist[record_index]["achievements"]:.4f}%"
                elif goal in combo_list:
                    if verlist[record_index]["fc"]:
                        self_record = combo_list[combo_list_raw.index(verlist[record_index]["fc"])]
                elif goal in sync_list:
                    if verlist[record_index]["fs"]:
                        self_record = sync_list[sync_list_raw.index(verlist[record_index]["fs"])]
            msg_chain.append(Plain(f"{s[0]} - {s[1]}{" (DX)" if s[5] == "DX" else ""} [{s[2]}] {s[3]} {self_record}"))
            if i == SONGS_PER_PAGE - 1:
                break
        if len(song_remain) > SONGS_PER_PAGE:
            msg_chain.append(
                I18NContext(
                    "maimai.message.process",
                    song_remain=len(song_remain),
                    level=level,
                    goal=goal))
        if len(song_remain) > SONGS_NEED_IMG:
            get_img = True
    else:
        await msg.finish(I18NContext("maimai.message.process.completed", level=level, goal=goal))

    return msg_chain, get_img


async def get_plate_process(msg: Bot.MessageSession, payload: dict, plate: str, use_cache: bool = True) -> tuple[
        MessageChain, bool]:
    song_played = []
    song_remain_basic = []
    song_remain_advanced = []
    song_remain_expert = []
    song_remain_master = []
    song_remain_remaster = []
    song_remain_difficult = []

    version = plate[0]
    goal = plate[1:]
    get_img = False

    if version in plate_version_ts_mapping:
        version = plate_version_ts_mapping[version]
    if goal in plate_goal_ts_mapping:
        goal = plate_goal_ts_mapping[goal]
    plate = version + goal

    if version == "真":  # 真代为无印版本
        payload["version"] = ["maimai", "maimai PLUS"]
    elif version in ["覇", "舞"]:  # 霸者和舞牌需要全版本
        payload["version"] = list(set(sd_plate_mapping.values()))
    elif version in plate_mapping and version != "初":  # “初”不是版本名称
        payload["version"] = [plate_mapping[version]]
    else:
        await msg.finish(I18NContext("maimai.message.plate.plate_not_found"))

    res: dict = await get_plate(msg, payload, version, use_cache)
    verlist = res["verlist"]

    if goal in ["将", "者"]:
        for song in verlist:  # 将剩余歌曲ID和难度加入目标列表
            if song["level_index"] == 0 and song["achievements"] < (100.0 if goal == "将" else 80.0):
                song_remain_basic.append((str(song["id"]), song["level_index"]))
            if song["level_index"] == 1 and song["achievements"] < (100.0 if goal == "将" else 80.0):
                song_remain_advanced.append((str(song["id"]), song["level_index"]))
            if song["level_index"] == 2 and song["achievements"] < (100.0 if goal == "将" else 80.0):
                song_remain_expert.append((str(song["id"]), song["level_index"]))
            if song["level_index"] == 3 and song["achievements"] < (100.0 if goal == "将" else 80.0):
                song_remain_master.append((str(song["id"]), song["level_index"]))
            if version in ["舞", "覇"] and str(song["id"]) in mai_plate_remaster_required and \
                    song["level_index"] == 4 and song["achievements"] < (100.0 if goal == "将" else 80.0):
                song_remain_remaster.append((str(song["id"]), song["level_index"]))  # 霸者和舞牌需要Re:MASTER难度
            song_played.append((str(song["id"]), song["level_index"]))
    elif goal == "極":
        for song in verlist:  # 将剩余歌曲ID和难度加入目标列表
            if song["level_index"] == 0 and not song["fc"]:
                song_remain_basic.append((str(song["id"]), song["level_index"]))
            if song["level_index"] == 1 and not song["fc"]:
                song_remain_advanced.append((str(song["id"]), song["level_index"]))
            if song["level_index"] == 2 and not song["fc"]:
                song_remain_expert.append((str(song["id"]), song["level_index"]))
            if song["level_index"] == 3 and not song["fc"]:
                song_remain_master.append((str(song["id"]), song["level_index"]))
            if version == "舞" and str(song["id"]) in mai_plate_remaster_required and \
                    song["level_index"] == 4 and not song["fc"]:
                song_remain_remaster.append((str(song["id"]), song["level_index"]))
            song_played.append((str(song["id"]), song["level_index"]))
    elif goal == "舞舞":
        for song in verlist:  # 将剩余歌曲ID和难度加入目标列表
            if song["level_index"] == 0 and song["fs"] not in ["fsd", "fsdp"]:
                song_remain_basic.append((str(song["id"]), song["level_index"]))
            if song["level_index"] == 1 and song["fs"] not in ["fsd", "fsdp"]:
                song_remain_advanced.append((str(song["id"]), song["level_index"]))
            if song["level_index"] == 2 and song["fs"] not in ["fsd", "fsdp"]:
                song_remain_expert.append((str(song["id"]), song["level_index"]))
            if song["level_index"] == 3 and song["fs"] not in ["fsd", "fsdp"]:
                song_remain_master.append((str(song["id"]), song["level_index"]))
            if version == "舞" and str(song["id"]) in mai_plate_remaster_required and \
                    song["level_index"] == 4 and song["fs"] not in ["fsd", "fsdp"]:
                song_remain_remaster.append((str(song["id"]), song["level_index"]))
            song_played.append((str(song["id"]), song["level_index"]))
    elif goal == "神":
        for song in verlist:  # 将剩余歌曲ID和难度加入目标列表
            if song["level_index"] == 0 and song["fc"] not in ["ap", "app"]:
                song_remain_basic.append((str(song["id"]), song["level_index"]))
            if song["level_index"] == 1 and song["fc"] not in ["ap", "app"]:
                song_remain_advanced.append((str(song["id"]), song["level_index"]))
            if song["level_index"] == 2 and song["fc"] not in ["ap", "app"]:
                song_remain_expert.append((str(song["id"]), song["level_index"]))
            if song["level_index"] == 3 and song["fc"] not in ["ap", "app"]:
                song_remain_master.append((str(song["id"]), song["level_index"]))
            if version == "舞" and str(song["id"]) in mai_plate_remaster_required and \
                    song["level_index"] == 4 and song["fc"] not in ["ap", "app"]:
                song_remain_remaster.append((str(song["id"]), song["level_index"]))
            song_played.append((str(song["id"]), song["level_index"]))
    else:
        await msg.finish(I18NContext("maimai.message.plate.plate_not_found"))

    for music in (await total_list.get()):  # 将未游玩歌曲ID加入目标列表
        if music["basic_info"]["from"] in payload["version"] and int(music.id) < 100000:  # 过滤宴谱
            if (music.id, 0) not in song_played:
                song_remain_basic.append((music.id, 0))
            if (music.id, 1) not in song_played:
                song_remain_advanced.append((music.id, 1))
            if (music.id, 2) not in song_played:
                song_remain_expert.append((music.id, 2))
            if (music.id, 3) not in song_played:
                song_remain_master.append((music.id, 3))
            if version in ["舞", "覇"] and len(music.level) == 5 and \
                    music.id in mai_plate_remaster_required and \
                    (music.id, 4) not in song_played:
                song_remain_remaster.append((music.id, 4))
    song_remain_basic = sorted(song_remain_basic, key=lambda i: int(i[0]))  # 根据ID排序结果
    song_remain_advanced = sorted(song_remain_advanced, key=lambda i: int(i[0]))
    song_remain_expert = sorted(song_remain_expert, key=lambda i: int(i[0]))
    song_remain_master = sorted(song_remain_master, key=lambda i: int(i[0]))
    song_remain_remaster = sorted(song_remain_remaster, key=lambda i: int(i[0]))
    for song in song_remain_basic + song_remain_advanced + \
            song_remain_expert + song_remain_master + song_remain_remaster:  # 循环查询歌曲信息
        music = (await total_list.get()).by_id(song[0])
        if music.ds[song[1]] > 13.6:  # 将难度为13+以上的谱面加入列表
            song_remain_difficult.append((music.id, music.title, diffs[song[1]],
                                          music.ds[song[1]], song[1], music.type))

    song_expect = mai_plate_song_expect(version)

    song_remain_basic = [music for music in song_remain_basic if music[0] not in song_expect]
    song_remain_advanced = [music for music in song_remain_advanced if music[0] not in song_expect]
    song_remain_expert = [music for music in song_remain_expert if music[0] not in song_expect]
    song_remain_master = [music for music in song_remain_master if music[0] not in song_expect]
    song_remain_remaster = [music for music in song_remain_remaster if music[0] not in song_expect]
    song_remain = song_remain_basic + song_remain_advanced + \
        song_remain_expert + song_remain_master + song_remain_remaster
    song_remain_difficult = [music for music in song_remain_difficult if music[0] not in song_expect]

    prompt = MessageChain.assign(I18NContext("maimai.message.plate.prompt", plate=plate))
    if song_remain_basic:
        prompt.append(I18NContext("maimai.message.plate.basic", song_remain=len(song_remain_basic)))
    if song_remain_advanced:
        prompt.append(I18NContext("maimai.message.plate.advanced", song_remain=len(song_remain_advanced)))
    if song_remain_expert:
        prompt.append(I18NContext("maimai.message.plate.expert", song_remain=len(song_remain_expert)))
    if song_remain_master:
        prompt.append(I18NContext("maimai.message.plate.master", song_remain=len(song_remain_master)))
    if version in ["舞", "覇"] and song_remain_remaster:  # 霸者和舞牌需要Re:MASTER难度
        prompt.append(I18NContext("maimai.message.plate.remaster", song_remain=len(song_remain_remaster)))

    if song_remain:
        await msg.send_message(prompt)

    song_record = [(str(s["id"]), s["level_index"]) for s in verlist]

    msg_chain = MessageChain.assign()
    if len(song_remain_difficult) > 0:
        if len(song_remain_difficult) < SONGS_PER_PAGE:
            msg_chain.append(I18NContext("maimai.message.plate.difficult.last"))
            for i, s in enumerate(sorted(song_remain_difficult, key=lambda i: i[3])):  # 根据定数排序结果
                self_record = ""
                if (s[0], s[-2]) in song_record:  # 显示剩余13+以上歌曲信息
                    record_index = song_record.index((s[0], s[-2]))
                    if goal in ["將", "者"]:
                        self_record = f"{verlist[record_index]["achievements"]:.4f}%"
                    elif goal in ["極", "神"]:
                        if verlist[record_index]["fc"]:
                            self_record = combo_list[combo_list_raw.index(verlist[record_index]["fc"])]
                    elif goal == "舞舞":
                        if verlist[record_index]["fs"]:
                            self_record = sync_list[sync_list_raw.index(verlist[record_index]["fs"])]
                msg_chain.append(Plain(f"{s[0]} - {s[1]}{" (DX)" if s[5] ==
                                                         "DX" else ""} [{s[2]}] {s[3]} {self_record}"))
            if len(song_remain_difficult) > SONGS_NEED_IMG:
                get_img = True
        else:
            msg_chain.append(I18NContext("maimai.message.plate.difficult", song_remain=len(song_remain_difficult)))
    elif len(song_remain) > 0:
        for i, s in enumerate(song_remain):
            m = (await total_list.get()).by_id(s[0])
            song_remain[i] = (s[0], s[1], m.ds[s[1]])
        if len(song_remain) < SONGS_PER_PAGE:
            msg_chain.append(I18NContext("maimai.message.plate.last"))
            for i, s in enumerate(sorted(song_remain, key=lambda i: i[2])):  # 根据难度排序结果
                m = (await total_list.get()).by_id(s[0])
                self_record = ""
                if [int(s[0]), s[-2]] in song_record:  # 显示剩余歌曲信息
                    record_index = song_record.index((s[0], s[-2]))
                    if goal in ["將", "者"]:
                        self_record = f"{verlist[record_index]["achievements"]:.4f}%"
                    elif goal in ["極", "神"]:
                        if verlist[record_index]["fc"]:
                            self_record = combo_list[combo_list_raw.index(verlist[record_index]["fc"])]
                    elif goal == "舞舞":
                        if verlist[record_index]["fs"]:
                            self_record = sync_list[sync_list_raw.index(verlist[record_index]["fs"])]
                msg_chain.append(Plain(f"{m.id} - {m.title}{" (DX)" if m.type ==
                                                            "DX" else ""} [{diffs[s[1]]}] {m.ds[s[1]]} {self_record}"))
            if len(song_remain) > SONGS_NEED_IMG:
                get_img = True
        else:
            msg_chain.append(I18NContext("maimai.message.plate.difficult.completed"))
    else:
        msg_chain.append(I18NContext("maimai.message.plate.completed", plate=plate))

    return msg_chain, get_img


async def get_grade_info(msg: Bot.MessageSession, grade: str):
    with open(mai_grade_info_path, "rb") as file:
        data = orjson.loads(file.read())

    def key_process(input_key, conv_dict):
        key = next((k for k, v in conv_dict.items() if input_key == k), None)
        if key is not None:
            value = conv_dict[key]
            new_key = next((k for k, v in conv_dict.items() if v == value), None)
            return value, new_key
        return None, input_key

    grade = grade.upper()  # 输入强制转换为大写以适配字典
    grade_key, grade = key_process(grade, grade_mapping)

    if not grade_key:
        await msg.finish(I18NContext("maimai.message.grade_invalid"))
    elif grade_key.startswith("tgrade"):
        grade_type = "tgrade"
    elif grade_key.startswith("grade"):
        grade_type = "grade"
    else:
        grade_type = "rgrade"

    chart_info = []
    grade_data = data[grade_type][grade_key]
    condition = grade_data["condition"]
    if grade_type != "rgrade":
        charts = grade_data["charts"]

        for chart in charts:
            music = (await total_list.get()).by_id(str(chart["id"]))
            level = chart["level_index"]
            chart_info.append(
                f"{
                    music["id"]} - {
                    music["title"]}{
                    " (DX)" if music["type"] == "DX" else ""} [{
                    diffs[level]}] {
                    music["level"][level]}")

    else:
        base = grade_data["base"]
        if "master" in grade_key:
            music_data_master = (await total_list.get()).filter(ds=(base[0], base[1]), diff=[3])
            music_data_remaster = (await total_list.get()).filter(ds=(base[0], base[1]), diff=[4])
            music_data = music_data_master + music_data_remaster

            for _ in range(4):
                music = Random.choice(music_data)
                if music in music_data_master and music in music_data_remaster:
                    level = Random.randint(3, 4)
                elif music in music_data_remaster:
                    level = 4
                else:
                    level = 3
                chart_info.append(
                    f"{
                        music["id"]} - {
                        music["title"]}{
                        " (DX)" if music["type"] == "DX" else ""} [{
                        diffs[level]}] {
                        music["level"][level]}")
        else:
            level = 2
            music_data = (await total_list.get()).filter(ds=(base[0], base[1]), diff=[level])
            for _ in range(4):
                music = music_data.random()
                chart_info.append(
                    f"{
                        music["id"]} - {
                        music["title"]}{
                        " (DX)" if music["type"] == "DX" else ""} [{
                        diffs[level]}] {
                        music["level"][level]}")

    content = "\n".join(chart_info)
    condition_info = f"GREAT{condition[0]}/GOOD{condition[1]}/MISS{condition[2]}/CLEAR{condition[3]}"

    await msg.finish(I18NContext("maimai.message.grade",
                                 grade=grade,
                                 content=content,
                                 life=grade_data["life"],
                                 condition=condition_info))
