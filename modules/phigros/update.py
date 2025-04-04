import csv
import os
import re
import shutil
import string
import traceback

import orjson as json

from core.constants.path import assets_path
from core.logger import Logger
from core.utils.cache import random_cache_path
from core.utils.http import get_url, download

pgr_assets_path = os.path.join(assets_path, "modules", "phigros")
rating_path = os.path.join(pgr_assets_path, "rating.json")
json_url = "https://raw.githubusercontent.com/ssmzhn/Phigros/main/Phigros.json"

p_headers = {
    "Accept": "application/json",
    "X-LC-Id": "rAK3FfdieFob2Nn8Am",
    "X-LC-Key": "Qr9AEqtuoSVS3zeD6iVbM4ZC0AtkJcQ89tywVyi0",
    "User-Agent": "LeanCloud-CSharp-SDK/1.0.3",
}


def remove_punctuations(text):
    punctuations = "！？｡＂＃＄％＆＇（）＊＋，－／：；＜＝＞＠［＼］＾＿｀｛｜｝～、。〃〈〉《》「」『』【】〒〔〕〖〗〘〙〚〛〜・♫☆×♪↑↓ "
    text = "".join(
        [
            char
            for char in text
            if char not in string.punctuation and char not in punctuations
        ]
    )
    text = re.sub(" +", " ", text)
    return text.lower()


async def update_assets():
    illustration_path = os.path.join(pgr_assets_path, "illustration")
    os.makedirs(illustration_path, exist_ok=True)
    illustration_list = os.listdir(illustration_path)
    file_path = f"{random_cache_path()}.json"
    data = {}
    try:
        update = await get_url(json_url, 200, fmt="json")
    except Exception:
        traceback.format_exc()
        return False
    if update:
        for song in update:
            diff = {}
            for c in update[song]["chart"]:
                diff[c] = update[song]["chart"][c]["difficulty"]
            data[
                remove_punctuations(update[song]["song"])
                + "."
                + remove_punctuations(update[song]["composer"])
            ] = diff

            song_name = remove_punctuations(update[song]["song"])
            if song_name not in illustration_list:
                try:
                    download_file = await download(update[song]["illustration_big"])
                    if download_file:
                        shutil.move(
                            download_file, os.path.join(illustration_path, song_name)
                        )
                except Exception:
                    pass
        Logger.success("Phigros illustrations download completed.")
    else:
        return False

    another_assets_url = "https://github.com/7aGiven/PhigrosLibrary/archive/refs/heads/master.zip"
    try:
        download_file = await download(another_assets_url)
    except Exception:
        traceback.format_exc()
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
                data[row[0].lower()] = {"EZ": row[1], "HD": row[2], "IN": row[3]}
                if len(row) > 4:
                    data[row[0].lower()]["AT"] = row[4]

        os.remove(download_file)
    else:
        return False
    with open(file_path, "wb") as f:
        f.write(json.dumps(data, option=json.OPT_INDENT_2))
    shutil.move(file_path, rating_path)
    return True
