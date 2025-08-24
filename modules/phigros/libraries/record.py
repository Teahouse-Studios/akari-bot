import os
import shutil
import struct

import orjson as json
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext
from core.constants.path import assets_path, cache_path
from core.logger import Logger
from core.utils.cache import random_cache_path
from core.utils.http import get_url, download
from .update import p_headers, remove_punctuations

pgr_assets_path = os.path.join(assets_path, "modules", "phigros")


levels = {
    "EZ": 1,
    "HD": 2,
    "IN": 4,
    "AT": 8,
}
secret = bytes(
    [
        232,
        150,
        154,
        210,
        165,
        64,
        37,
        155,
        151,
        145,
        144,
        139,
        136,
        230,
        191,
        3,
        30,
        109,
        33,
        149,
        110,
        250,
        214,
        138,
        80,
        221,
        85,
        214,
        122,
        176,
        146,
        75,
    ]
)
iv = bytes([42, 79, 240, 138, 200, 13, 99, 7, 0, 87, 197, 149, 24, 200, 50, 83])


def decrypt_bytes(encrypted):
    cipher = AES.new(key=secret, mode=AES.MODE_CBC, IV=iv)
    decrypted = cipher.decrypt(encrypted[1:])
    return unpad(decrypted, AES.block_size)


def parse_game_record(rd_path):
    with open(os.path.join(pgr_assets_path, "song_info.json"), "rb") as f:
        song_info = json.loads(f.read())
    decrypted_data = {}
    with open(os.path.join(rd_path, "gameRecord"), "rb+") as rd:
        data = decrypt_bytes(rd.read())
        pos = int(data[0] < 0) + 1
        while pos < len(data):
            name_length = data[pos]
            pos += 1
            if name_length == 1:
                continue
            song_id = data[pos: (pos + name_length)]
            song_id = song_id.decode("utf-8").removesuffix(".0").lower()
            sid_split = song_id.split(".", 1)
            if len(sid_split) == 2:
                song_id = f"{remove_punctuations(sid_split[0])}.{remove_punctuations(sid_split[1])}"
            else:
                song_id = remove_punctuations(sid_split[0])

            pos += name_length
            score_length = data[pos]
            pos += 1

            score = data[pos: (pos + score_length)]
            pos += score_length

            has_score = score[0]
            full_combo = score[1]
            score_pos = 2

            record = {}

            for diff, digit in levels.items():
                if (has_score & digit) == digit:
                    record[diff] = {
                        "score": int.from_bytes(
                            score[score_pos: (score_pos + 4)],
                            byteorder="little",
                            signed=True,
                        ),
                        "accuracy": struct.unpack(
                            "<f", score[(score_pos + 4): (score_pos + 8)]
                        )[0],
                        "full_combo": (full_combo & digit) == digit,
                    }
                    if song_id in song_info and diff in song_info[song_id]["diff"]:
                        record[diff]["base_rks"] = float(song_info[song_id]["diff"][diff])
                        if record[diff]["score"] == 1000000:
                            record[diff]["rks"] = float(song_info[song_id]["diff"][diff])
                        elif record[diff]["accuracy"] < 70:
                            record[diff]["rks"] = 0
                        else:
                            record[diff]["rks"] = (((record[diff]["accuracy"] - 55) / 45) ** 2) * \
                                float(song_info[song_id]["diff"][diff])
                    else:
                        del record[diff]
                    score_pos += 8
            if not decrypted_data.get(song_id):
                decrypted_data[song_id] = {}
            if song_info.get(song_id) and song_info[song_id]["name"]:
                decrypted_data[song_id]["name"] = song_info[song_id]["name"]
            else:
                decrypted_data[song_id]["name"] = song_id.split(".")[0]
            decrypted_data[song_id]["diff"] = record
    return decrypted_data


async def get_game_record(msg: Bot.MessageSession, session_token: str, use_cache: bool = True):
    pgr_cache_path = os.path.join(cache_path, "phigros-record")
    os.makedirs(pgr_cache_path, exist_ok=True)
    cache_dir = os.path.join(
        pgr_cache_path, f"{msg.session_info.sender_id.replace("|", "_")}_phigros_song_record.json"
    )
    save_filename = f"{msg.session_info.sender_id.replace("|", "_")}_phigros_gamesave"
    save_dir = os.path.join(pgr_cache_path, save_filename)

    save_url = "https://rak3ffdi.cloud.tds1.tapapis.cn/1.1/classes/_GameSave"
    headers = p_headers.copy()
    headers["X-LC-Session"] = session_token
    try:
        get_save_url = await get_url(save_url, headers=headers, fmt="json")
        save_url = get_save_url["results"][0]["gameFile"]["url"]

        dl = await download(save_url, f"{save_filename}.zip", pgr_cache_path)
        shutil.unpack_archive(dl, save_dir)
        data = parse_game_record(save_dir)
        os.remove(os.path.join(pgr_cache_path, f"{save_filename}.zip"))

        if use_cache and data:
            if os.path.exists(cache_dir):
                with open(cache_dir, "rb") as f:
                    try:
                        backup_data = json.loads(f.read())
                    except Exception:
                        backup_data = {}
            else:
                backup_data = {}
            backup_data.update(data)
            with open(cache_dir, "wb") as f:
                f.write(json.dumps(backup_data))
        return data
    except Exception as e:
        Logger.exception()
        if use_cache and os.path.exists(cache_dir):
            try:
                with open(cache_dir, "rb") as f:
                    data = json.loads(f.read())
                await msg.send_message(I18NContext("phigros.message.use_cache"))
                return data
            except Exception:
                raise e
        else:
            raise e
