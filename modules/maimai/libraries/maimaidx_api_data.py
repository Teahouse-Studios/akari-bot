import os
import shutil

import ujson as json

from core.logger import Logger
from core.utils.cache import random_cache_path
from core.utils.http import get_url, post_url, download_to_cache
from .maimaidx_music import get_cover_len5_id, TotalList

total_list = TotalList()

assets_path = os.path.abspath('./assets/maimai')
cover_dir = f"{assets_path}/static/mai/cover"


async def update_assets():
    try:
        alias_url = "https://download.fanyu.site/maimai/alias.json"
        input_data = await get_url(alias_url, 200, fmt='json')

        output_data = {}
        for key, values in input_data.items():
            for value in values:
                if value == "未找到":
                    continue
                if value not in output_data:
                    output_data[value] = []
                output_data[value].append(key)

        output_data = {k: output_data[k] for k in sorted(output_data)}

        file_path = os.path.join(assets_path, "mai_alias.json")
        with open(file_path, 'w') as file:
            json.dump(output_data, file)
    except:
        return False
        
    Logger.info('Maimai alias download completed.')
    
    try:
            static_url = f"https://www.diving-fish.com/maibot/static.zip"
            download_file = await download_to_cache(static_url, timeout=60)

            ca = random_cache_path()
            shutil.unpack_archive(download_file, ca)
        
            if os.path.exists(cover_dir):
                shutil.rmtree(cover_dir)
        
            static_cover_dir = os.path.join(ca, 'mai/cover')
            if os.path.exists(static_cover_dir):
                shutil.move(static_cover_dir, cover_dir)

            os.remove(download_file)
    except:
            return False
                
    Logger.info('Maimai covers download completed.')
    
    return True


async def get_alias(msg, input, get_music=False):
    file_path = os.path.join(assets_path, "mai_alias.json")

    if not os.path.exists(file_path):
        await msg.finish(msg.locale.t("maimai.message.alias.file_not_found", prefix=msg.prefixes[0]))
    with open(file_path, 'r') as file:
        data = json.load(file)

    result = []
    if get_music:
        for alias, ids in data.items():
            if input in ids:
                result.append(alias)
    else:
        input = input.replace("_", " ")
        if input in data:
            result = data[input]
    
    return result


async def get_record(msg, payload):
    url = f"https://www.diving-fish.com/api/maimaidxprober/query/player"
    try:
        data = await post_url(url,
                              data=json.dumps(payload),
                              status_code=200,
                              headers={'Content-Type': 'application/json', 'accept': '*/*'}, fmt='json')
    except ValueError as e:
        if str(e).startswith('400'):
            if "qq" in payload:
                await msg.finish(msg.locale.t("maimai.message.user_unbound"))
            else:
                await msg.finish(msg.locale.t("maimai.message.user_not_found"))
        if str(e).startswith('403'):
            await msg.finish(msg.locale.t("maimai.message.forbidden"))

    return data


async def get_plate(msg, payload):
    url = f"https://www.diving-fish.com/api/maimaidxprober/query/plate"
    try:
        data = await post_url(url,
                              data=json.dumps(payload),
                              status_code=200,
                              headers={'Content-Type': 'application/json', 'accept': '*/*'}, fmt='json')
    except ValueError as e:
        if str(e).startswith('400'):
            if "qq" in payload:
                await msg.finish(msg.locale.t("maimai.message.user_unbound"))
            else:
                await msg.finish(msg.locale.t("maimai.message.user_not_found"))
        if str(e).startswith('403'):
            await msg.finish(msg.locale.t("maimai.message.forbidden"))

    return data


def get_cover(sid):
    cover_url = f"https://www.diving-fish.com/covers/{get_cover_len5_id(sid)}.png"
    cover_path = f"{cover_dir}/{get_cover_len5_id(sid)}.png"
    if os.path.exists(os.path.abspath(cover_path)):
        return os.path.abspath(cover_path)
    else:
        return cover_url
