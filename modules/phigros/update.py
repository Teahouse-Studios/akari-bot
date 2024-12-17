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

pgr_assets_path = os.path.join(assets_path, "phigros")
rating_path = os.path.join(pgr_assets_path, "rating.json")
json_url = "https://raw.githubusercontent.com/ssmzhn/Phigros/main/Phigros.json"
json_url_mirror = "https://gh.api.99988866.xyz/https://raw.githubusercontent.com/ssmzhn/Phigros/main/Phigros.json"

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
        update = await get_url(json_url, 200)
    except TimeoutError:
        try:
            update = await get_url(json_url_mirror, 200)
        except BaseException:
            return False
    update_json = json.loads(update)
    for song in update_json:
        diff = {}
        for c in update_json[song]["chart"]:
            diff[c] = update_json[song]["chart"][c]["difficulty"]
        data[
            remove_punctuations(update_json[song]["song"])
            + "."
            + remove_punctuations(update_json[song]["composer"])
        ] = diff

        song_name = remove_punctuations(update_json[song]["song"])
        if song_name not in illustration_list:
            try:
                download_file = await download(update_json[song]["illustration"])
                if download_file:
                    shutil.move(
                        download_file, os.path.join(illustration_path, song_name)
                    )
            except Exception:
                shutil.copy(
                    os.path.join(pgr_assets_path, "unknown"),
                    os.path.join(illustration_path, song_name),
                )
    Logger.info("Phigros illustrations download completed.")
    another_assets_url = (
        "https://github.com/7aGiven/PhigrosLibrary/archive/refs/heads/master.zip"
    )
    another_assets_url_mirror = "https://gh.api.99988866.xyz/https://github.com/7aGiven/PhigrosLibrary/archive/refs/heads/master.zip"
    try:
        download_file = await download(another_assets_url)
    except TimeoutError:
        download_file = await download(another_assets_url_mirror)
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
    with open(file_path, "wb", encoding="utf-8") as f:
        f.write(json.dumps(data, option=json.OPT_INDENT_2))
    shutil.move(file_path, rating_path)
    return True
