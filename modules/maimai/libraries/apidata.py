import os
import shutil
import traceback
import ujson as json

from core.builtins import Bot, Plain, Image
from core.logger import Logger
from core.utils.cache import random_cache_path
from core.utils.http import get_url, post_url, download_to_cache
from .music import get_cover_len5_id, Music, TotalList

assets_path = os.path.abspath('./assets/maimai')
total_list = TotalList()


async def update_alias():
    url = "https://download.fanyu.site/maimai/alias.json"
    data = await get_url(url, 200, fmt='json')
    
    file_path = os.path.join(assets_path, "mai_alias.json")
    with open(file_path, 'w') as file:
        json.dump(data, file)
        
    return True


async def update_covers():
    cover_dir = f"{assets_path}/static/mai/cover"
    url = f"https://www.diving-fish.com/maibot/static.zip"
    download_file = await download_to_cache(url, timeout=60)

    Logger.info('Maimai covers download completed.')
    ca = random_cache_path()
    shutil.unpack_archive(download_file, ca)

    if os.path.exists(cover_dir):
        shutil.rmtree(cover_dir)
        
    static_cover_dir = os.path.join(ca, 'mai/cover')
    if os.path.exists(static_cover_dir):
        shutil.move(static_cover_dir, cover_dir)

    os.remove(download_file)

    return True


async def get_info(msg: Bot.MessageSession, music: Music, *details):
    info = [Plain(f"{music.id}\u200B. {music.title}{' (DX)' if music['type'] == 'DX' else ''}")]
    try:
        img = f"https://www.diving-fish.com/covers/{get_cover_len5_id(music.id)}.png"
        await get_url(img, 200, attempt=1, fmt='read')
        info.append(Image(img))
    except:
        info.append(Image("https://www.diving-fish.com/covers/00000.png"))
    if details:
        info.extend(details)
    return info


async def get_alias(msg, sid):
    file_path = os.path.join(assets_path, "mai_alias.json")

    if not os.path.exists(file_path):
        await msg.finish(msg.locale.t("maimai.message.alias.file_not_found", prefix=msg.prefixes[0]))
    with open(file_path, 'r') as file:
        data = json.load(file)

    result = []
    if sid in data:
        result = data[sid] # 此处的列表是歌曲别名列表
    
    return result


async def search_by_alias(msg, input_):
    result = []
    input_ = input_.replace("_", " ").strip().lower()
    res = (await total_list.get()).filter(title=input_)
    for s in res:
        result.append(s['id'])

    file_path = os.path.join(assets_path, "mai_alias.json")

    if not os.path.exists(file_path):
        return result

    with open(file_path, 'r') as file:
        data = json.load(file)

    for sid, aliases in data.items():
        aliases = [alias.lower() for alias in aliases]
        if input_ in aliases:
            if sid in result:
                result.remove(sid)
            result.append(sid) # 此处的列表是歌曲 ID 列表
    
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
        elif str(e).startswith('403'):
            if "qq" in payload:
                await msg.finish(msg.locale.t("maimai.message.forbidden.eula"))
            else:
                await msg.finish(msg.locale.t("maimai.message.forbidden"))
        else:
            traceback.print_exc()

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
        elif str(e).startswith('403'):
            if "qq" in payload:
                await msg.finish(msg.locale.t("maimai.message.forbidden.eula"))
            else:
                await msg.finish(msg.locale.t("maimai.message.forbidden"))
            
    return data
