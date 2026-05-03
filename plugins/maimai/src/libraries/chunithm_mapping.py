from core.config import Config
from core.constants.path import assets_path

DF_DEVELOPER_TOKEN = Config("diving_fish_developer_token", cfg_type=str, secret=True, table_name="module_maimai")
LX_DEVELOPER_TOKEN = Config("lxns_developer_token", cfg_type=str, secret=True, table_name="module_maimai")
SONGS_PER_PAGE = 30

default_source = "lxns" if LX_DEVELOPER_TOKEN else "diving-fish"

mai_assets_path = assets_path / "modules" / "maimai"
chu_cover_path = mai_assets_path / "static" / "chu" / "cover"
chu_song_info_path = mai_assets_path / "chu_song_info.json"

score_to_rate = {
    (0, 499999): "D",
    (500000, 599999): "C",
    (600000, 699999): "B",
    (700000, 799999): "BB",
    (800000, 899999): "BBB",
    (900000, 924999): "A",
    (925000, 949999): "AA",
    (950000, 974999): "AAA",
    (975000, 989999): "S",
    (990000, 999999): "S+",
    (1000000, 1004999): "SS",
    (1005000, 1007499): "SS+",
    (1007500, 1008999): "SSS",
    (1009000, 1010000): "SSS+",
}

combo_mapping = {"fullcombo": "FULL COMBO", "alljustice": "ALL JUSTICE"}

diff_list = ["Basic", "Advanced", "Expert", "Master", "Ultima"]
diff_list_abbr = ["bas", "adv", "exp", "mas", "ult"]
diff_list_zhs = ["绿", "黄", "红", "紫", "黑"]
diff_list_zht = ["綠", "黃", "紅", "紫", "黑"]
