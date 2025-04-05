import os

from core.config import Config
from core.constants.path import assets_path

DEVELOPER_TOKEN = Config("diving_fish_developer_token", cfg_type=str, secret=True, table_name="module_maimai")
SONGS_PER_PAGE = 30
SONGS_NEED_IMG = 10

mai_assets_path = os.path.join(assets_path, "modules", "maimai")
mai_cover_path = os.path.join(mai_assets_path, "static", "mai", "cover")
mai_alias_path = os.path.join(mai_assets_path, "mai_song_alias.json")
mai_grade_info_path = os.path.join(mai_assets_path, "mai_grade_info.json")
mai_song_info_path = os.path.join(mai_assets_path, "mai_song_info.json")
mai_utage_info_path = os.path.join(mai_assets_path, "mai_utage_info.json")

achievement_list = [
    50.0,
    60.0,
    70.0,
    75.0,
    80.0,
    90.0,
    94.0,
    97.0,
    98.0,
    99.0,
    99.5,
    100.0,
    100.5,
]
rate_list = [
    "D",
    "C",
    "B",
    "BB",
    "BBB",
    "A",
    "AA",
    "AAA",
    "S",
    "S+",
    "SS",
    "SS+",
    "SSS",
    "SSS+",
]
rate_list_raw = [
    "d",
    "c",
    "b",
    "bb",
    "bbb",
    "a",
    "aa",
    "aaa",
    "s",
    "sp",
    "ss",
    "ssp",
    "sss",
    "sssp",
]
score_to_rate = {
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
    (100.5, float("inf")): "SSS+",
}

rate_mapping = {
    "d": "D",
    "c": "C",
    "b": "B",
    "bb": "BB",
    "bbb": "BBB",
    "a": "A",
    "aa": "AA",
    "aaa": "AAA",
    "s": "S",
    "sp": "S+",
    "ss": "SS",
    "ssp": "SS+",
    "sss": "SSS",
    "sssp": "SSS+",
}

combo_list = ["FC", "FC+", "AP", "AP+"]
combo_list_raw = ["fc", "fcp", "ap", "app"]
combo_mapping = {
    "fc": "FC",
    "fcp": "FC+",
    "ap": "AP",
    "app": "AP+",
}

sync_list = ["SYNC", "FS", "FS+", "FSD", "FSD+"]
sync_list_raw = ["sync", "fs", "fsp", "fsd", "fsdp"]
sync_mapping = {
    "sync": "SYNC",
    "fs": "FS",
    "fsp": "FS+",
    "fsd": "FDX",
    "fsdp": "FDX+",
}

diff_list = ["Basic", "Advanced", "Expert", "Master", "Re:MASTER"]
diff_list_abbr = ["bas", "adv", "exp", "mas", "rem"]
diff_list_zhs = ["绿", "黄", "红", "紫", "白"]
diff_list_zht = ["綠", "黃", "紅", "紫", "白"]
diffs = {
    0: "Basic",
    1: "Advanced",
    2: "Expert",
    3: "Master",
    4: "Re:MASTER",
}

level_list = [
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "7+",
    "8",
    "8+",
    "9",
    "9+",
    "10",
    "10+",
    "11",
    "11+",
    "12",
    "12+",
    "13",
    "13+",
    "14",
    "14+",
    "15",
]
goal_list = [
    "A",
    "AA",
    "AAA",
    "S",
    "S+",
    "SS",
    "SS+",
    "SSS",
    "SSS+",
    "FC",
    "FC+",
    "AP",
    "AP+",
    "FS",
    "FS+",
    "FDX",
    "FDX+",
]

genre_i18n_mapping = {
    "流行&动漫": "POPS & ANIME",
    "POPSアニメ": "POPS & ANIME",
    "niconicoボーカロイド": "niconico & VOCALOID",
    "东方Project": "東方Project",
    "其他游戏": "GAME & VARIETY",
    "ゲームバラエティ": "GAME & VARIETY",
    "舞萌": "maimai",
    "音击&中二节奏": "ONGEKI & CHUNITHM",
    "オンゲキCHUNITHM": "ONGEKI & CHUNITHM",
}

mai_plate_remaster_required = [
    17,
    22,
    23,
    24,
    58,
    61,
    62,
    65,
    66,
    70,
    71,
    80,
    81,
    100,
    107,
    143,
    145,
    198,
    200,
    204,
    226,
    227,
    247,
    255,
    256,
    265,
    266,
    282,
    295,
    296,
    299,
    301,
    310,
    312,
    365,
    414,
    496,
    513,
    532,
    589,
    741,
    756,
    759,
    763,
    777,
    793,
    799,
    803,
    806,
    809,
    812,
    816,
    818,
    820,
    825,
    830,
    833,
    834,
    838,
]

versions = [
    "maimai",
    "maimai PLUS",
    "maimai GreeN",
    "maimai GreeN PLUS",
    "maimai ORANGE",
    "maimai ORANGE PLUS",
    "maimai PiNK",
    "maimai PiNK PLUS",
    "maimai MURASAKi",
    "maimai MURASAKi PLUS",
    "maimai MiLK",
    "MiLK PLUS",
    "maimai FiNALE",
    "maimai でらっくす",
    "maimai でらっくす Splash",
    "maimai でらっくす UNiVERSE",
    "maimai でらっくす FESTiVAL",
    "maimai でらっくす BUDDiES",
]

sd_plate_mapping = {
    "初": "maimai",
    "真": "maimai PLUS",
    "超": "maimai GreeN",
    "檄": "maimai GreeN PLUS",
    "橙": "maimai ORANGE",
    "暁": "maimai ORANGE PLUS",
    "桃": "maimai PiNK",
    "櫻": "maimai PiNK PLUS",
    "紫": "maimai MURASAKi",
    "菫": "maimai MURASAKi PLUS",
    "白": "maimai MiLK",
    "雪": "MiLK PLUS",
    "輝": "maimai FiNALE",
}

dx_plate_mapping = {
    "熊": "maimai でらっくす",
    "華": "maimai でらっくす",
    "爽": "maimai でらっくす Splash",
    "煌": "maimai でらっくす Splash",
    "宙": "maimai でらっくす UNiVERSE",
    "星": "maimai でらっくす UNiVERSE",
    "祭": "maimai でらっくす FESTiVAL",
    "祝": "maimai でらっくす FESTiVAL",
    "双": "maimai でらっくす BUDDiES",
    "宴": "maimai でらっくす BUDDiES",
}

plate_mapping = sd_plate_mapping | dx_plate_mapping

plate_version_ts_mapping = {"霸": "覇", "晓": "暁", "樱": "櫻", "堇": "菫", "辉": "輝", "华": "華", "雙": "双"}
plate_goal_ts_mapping = {"將": "将", "极": "極"}

grade_mapping = {
    "初段": "grade1",
    "二段": "grade2",
    "三段": "grade3",
    "四段": "grade4",
    "五段": "grade5",
    "六段": "grade6",
    "七段": "grade7",
    "八段": "grade8",
    "九段": "grade9",
    "十段": "grade10",
    "真初段": "tgrade1",
    "真二段": "tgrade2",
    "真三段": "tgrade3",
    "真四段": "tgrade4",
    "真五段": "tgrade5",
    "真六段": "tgrade6",
    "真七段": "tgrade7",
    "真八段": "tgrade8",
    "真九段": "tgrade9",
    "真十段": "tgrade10",
    "真皆伝": "tgrade11",
    "真皆传": "tgrade11",
    "真皆傳": "tgrade11",
    "裏皆伝": "tgrade12",
    "里皆传": "tgrade12",
    "裡皆傳": "tgrade12",
    "裏皆傳": "tgrade12",
    "EXPERT初級": "expert1",
    "EXPERT初级": "expert1",
    "EXPERT中級": "expert2",
    "EXPERT中级": "expert2",
    "EXPERT上級": "expert3",
    "EXPERT上级": "expert3",
    "EXPERT超上級": "expert4",
    "EXPERT超上级": "expert4",
    "MASTER初級": "master1",
    "MASTER初级": "master1",
    "MASTER中級": "master2",
    "MASTER中级": "master2",
    "MASTER上級": "master3",
    "MASTER上级": "master3",
    "MASTER超上級": "master4",
    "MASTER超上级": "master4",
}


def mai_plate_song_expect(version):
    match version:
        case "真":
            song_expect = [70, 146]
        case "超":
            song_expect = [185, 189, 190]
        case "檄":
            song_expect = [341]
        case "暁":
            song_expect = [419]
        case "桃":
            song_expect = [451, 455, 460]
        case "櫻":
            song_expect = [524]
        case "菫":
            song_expect = [853]
        case "白":
            song_expect = [687, 688, 712]
        case "雪":
            song_expect = [731]
        case "輝":
            song_expect = [792]
        case "覇" | "舞":
            song_expect = [146, 185, 189, 190, 341, 419, 451, 455, 460, 524, 687, 688, 712, 731, 792, 853]
        case "熊" | "華":
            song_expect = [10146]
        case "爽" | "煌":
            song_expect = [11213]
        case "宙" | "星":
            song_expect = [11253, 11267]
        case _:
            song_expect = []
    return song_expect
