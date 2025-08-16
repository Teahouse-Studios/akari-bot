import csv
import os
import re
import shutil
import string

import orjson as json

from core.constants.path import assets_path
from core.logger import Logger
from core.utils.cache import random_cache_path
from core.utils.http import get_url, download

pgr_assets_path = os.path.join(assets_path, "modules", "phigros")
song_info_path = os.path.join(pgr_assets_path, "song_info.json")
json_url = "https://raw.githubusercontent.com/ssmzhn/Phigros/main/Phigros.json"

p_headers = {
    "Accept": "application/json",
    "X-LC-Id": "rAK3FfdieFob2Nn8Am",
    "X-LC-Key": "Qr9AEqtuoSVS3zeD6iVbM4ZC0AtkJcQ89tywVyi0",
    "User-Agent": "LeanCloud-CSharp-SDK/1.0.3",
}


def remove_punctuations(text):
    punctuations = "！？｡＂＃＄％＆＇（）＊＋，－／：；＜＝＞＠［＼］＾＿｀｛｜｝～、。〃〈〉《》「」『』【】〒〔〕〖〗〘〙〚〛〜・♫☆×♪↑↓²³ "
    text = "".join(
        [
            char
            for char in text
            if char not in string.punctuation and char not in punctuations
        ]
    )
    text = re.sub(" +", " ", text)
    return text.lower()


async def update_assets(update_cover=True):
    file_path = f"{random_cache_path()}.json"
    data = {}
    illustration_path = os.path.join(pgr_assets_path, "illustration")
    os.makedirs(illustration_path, exist_ok=True)
    illustration_list = os.listdir(illustration_path)
    try:
        update = await get_url(json_url, 200, fmt="json")
    except Exception:
        Logger.exception()
        return False
    if update:
        for song in update:
            song_full_id = f"{
                remove_punctuations(
                    update[song]["song"])}.{
                remove_punctuations(
                    update[song]["composer"])}"
            if not data.get(song_full_id):
                data[song_full_id] = {}
            data[song_full_id]["name"] = update[song]["song"]
            data[song_full_id]["composer"] = update[song]["composer"]
            diff = {}
            for c in update[song]["chart"]:
                diff[c] = update[song]["chart"][c]["difficulty"]
            data[song_full_id]["diff"] = diff

            if update_cover:
                song_id = remove_punctuations(update[song]["song"])
                if song_id not in illustration_list:
                    try:
                        download_file = await download(update[song]["illustration_big"], f"{song_id}.png")
                        if download_file:
                            shutil.move(
                                download_file, os.path.join(illustration_path, f"{song_id}.png")
                            )
                    except Exception:
                        pass
                else:
                    return False

        if update_cover:
            Logger.success("Phigros illustrations download completed.")

    with open(file_path, "wb") as f:
        f.write(json.dumps(data, option=json.OPT_INDENT_2))
    shutil.move(file_path, song_info_path)
    return True
"""
    another_assets_url = "https://github.com/7aGiven/PhigrosLibrary/archive/refs/heads/master.zip"
    try:
        download_file = await download(another_assets_url)
    except Exception:
        Logger.exception()
        return False
    if download_file:
        ca = random_cache_path()
        shutil.unpack_archive(download_file, ca)

        with open(
            os.path.join(ca, "PhigrosLibrary-main", "difficulty.tsv"),
            "r",
            encoding="utf-8",
        ) as f:
            reader = csv.reader(f, delimiter="\t")
            for row in reader:
                sid_split = row[0].lower().split(".", 1)
                sid = f"{sid_split[0]}.{sid_split[1]}"
                if not data.get(sid):
                    data[sid] = {}
                data[sid]["diff"] = {"EZ": row[1], "HD": row[2], "IN": row[3]}
                if len(row) > 4:
                    data[sid]["diff"]["AT"] = row[4]

        with open(
            os.path.join(ca, "PhigrosLibrary-main", "info.tsv"),
            "r",
            encoding="utf-8",
        ) as f:
            reader = csv.reader(f, delimiter="\t")
            for row in reader:
                sid_split = row[0].lower().split(".", 1)
                sid = f"{remove_punctuations(sid_split[0])}.{remove_punctuations(sid_split[1])}"
                if not data.get(sid):
                    data[sid] = {}
                data[sid]["name"] = row[1]
                data[sid]["composer"] = row[2]

        os.remove(download_file)
    else:
        return False
"""
