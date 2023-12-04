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


async def get_alias(msg, input_):
    file_path = os.path.join(assets_path, "mai_alias.json")

    if not os.path.exists(file_path):
        await msg.finish(msg.locale.t("maimai.message.alias.file_not_found", prefix=msg.prefixes[0]))
    with open(file_path, 'r') as file:
        data = json.load(file)

    result = []
    if input_ in data:
        result = data[input_] # 此处的列表是歌曲别名列表
    
    return result


async def search_by_alias(msg, input_):
    result = []
    input_ = input_.replace("_", " ").strip()
    res = (await total_list.get()).filter(title=input_)
    for s in res:
        result.append(s['id'])

    file_path = os.path.join(assets_path, "mai_alias.json")

    if not os.path.exists(file_path):
        return result

    with open(file_path, 'r') as file:
        data = json.load(file)

    for alias, ids in data.items():
        if input_ in ids:
            if alias in result:
                result.remove(alias)
            result.append(alias) # 此处的列表是歌曲 ID 列表
    
    return result


async def get_record(msg, payload):
    url = f"https://www.diving-fish.com/api/maimaidxprober/query/player"
    try:
        data = await post_url(url,
                              data=json.dumps(payload),
                              status_code=200,
                              headers={'Content-Type': 'application/json', 'accept': '*/*'}, fmt='json')
    except Exception as e:
        if str(e).startswith('400'):
            if "qq" in payload:
                await msg.finish(msg.locale.t("maimai.message.user_unbound"))
            else:
                await msg.finish(msg.locale.t("maimai.message.user_not_found"))
        elif str(e).startswith('403'):
            await msg.finish(msg.locale.t("maimai.message.forbidden"))
        else:
            await msg.finish(ErrorMessage(str(e)))
    return data


async def get_plate(msg, payload):
    url = f"https://www.diving-fish.com/api/maimaidxprober/query/plate"
    try:
        data = await post_url(url,
                              data=json.dumps(payload),
                              status_code=200,
                              headers={'Content-Type': 'application/json', 'accept': '*/*'}, fmt='json')
    except Exception as e:
        if str(e).startswith('400'):
            if "qq" in payload:
                await msg.finish(msg.locale.t("maimai.message.user_unbound"))
            else:
                await msg.finish(msg.locale.t("maimai.message.user_not_found"))
        elif str(e).startswith('403'):
            await msg.finish(msg.locale.t("maimai.message.forbidden"))
        else:
            await msg.finish(ErrorMessage(str(e)))
    return data
