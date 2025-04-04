import os
import traceback
from typing import Optional, Union

import orjson as json
from langconv.converter import LanguageConverter
from langconv.language.zh import zh_cn

from core.builtins import Bot, Image, MessageChain, Plain
from core.constants.exceptions import ConfigValueError
from core.constants.path import cache_path
from core.logger import Logger
from core.utils.http import download, get_url, post_url
from core.utils.text import isint
from .maimaidx_mapping import *
from .maimaidx_music import get_cover_len5_id, Music, TotalList

total_list = TotalList()


async def update_cover() -> bool:
    id_list = ["0", "1000"]
    for song in await total_list.get():
        id_list.append(song["id"])
    os.makedirs(mai_cover_path, exist_ok=True)
    for id in id_list:
        cover_path = os.path.join(mai_cover_path, f"{id}.png")
        if not os.path.exists(cover_path):
            try:
                url = f"https://www.diving-fish.com/covers/{get_cover_len5_id(id)}.png"
                await download(
                    url,
                    status_code=200,
                    path=mai_cover_path,
                    filename=f"{id}.png",
                    attempt=1,
                    logging_err_resp=False,
                )
                Logger.debug(f"Successfully download {id}.png")
            except Exception as e:
                if str(e).startswith("404"):
                    if Config("debug", False):
                        Logger.error(f"Failed to download {id}.png")
                    continue
                Logger.error(traceback.format_exc())
                return False
    return True


async def update_alias() -> bool:
    try:
        url = "https://download.xraybot.site/maimai/alias.json"
        data = await get_url(url, 200, fmt="json")

        with open(mai_alias_path, "wb") as file:
            file.write(json.dumps(data, option=json.OPT_INDENT_2))
    except Exception:
        Logger.error(traceback.format_exc())
        return False
    return True


async def get_info(music: Music, *details) -> MessageChain:
    info = [
        Plain(f"{music.id} - {music.title}{" (DX)" if music["type"] == "DX" else ""}")
    ]
    cover_path = os.path.join(mai_cover_path, f"{music.id}.png")
    if os.path.exists(cover_path):
        info.append(Image(cover_path))
    else:
        cover_path = os.path.join(mai_cover_path, "0.png")
        if os.path.exists(cover_path):
            info.append(Image(cover_path))
    if details:
        info.extend(details)
    return info


async def get_alias(msg: Bot.MessageSession, sid: str) -> list:
    if not os.path.exists(mai_alias_path):
        await msg.finish(
            msg.locale.t("maimai.message.alias.file_not_found", prefix=msg.prefixes[0])
        )
    with open(mai_alias_path, "r", encoding="utf-8") as file:
        data = json.loads(file.read())

    result = []
    if sid in data:
        result = data[sid]  # 此处的列表是歌曲别名列表
        result = sorted(result)
    return result


async def search_by_alias(input_: str) -> list:
    result = []
    convinput = LanguageConverter.from_language(zh_cn).convert(input_)
    res = (await total_list.get()).filter(title=input_)
    for s in res:
        result.append(s["id"])
    if isint(input_):
        music = (await total_list.get()).by_id(input_)
        if music:
            result.append(input_)

    if not os.path.exists(mai_alias_path):
        return list(set(result))

    with open(mai_alias_path, "r", encoding="utf-8") as file:
        data = json.loads(file.read())

    for sid, aliases in data.items():
        aliases = [alias.lower() for alias in aliases]
        if input_ in aliases or convinput in aliases:
            result.append(sid)  # 此处的列表是歌曲 ID 列表

    return list(set(result))


async def get_record(
    msg: Bot.MessageSession, payload: dict, use_cache: bool = True
) -> Optional[str]:
    mai_cache_path = os.path.join(cache_path, "maimai-record")
    os.makedirs(mai_cache_path, exist_ok=True)
    cache_dir = os.path.join(
        mai_cache_path, f"{msg.target.sender_id.replace("|", "_")}_maimaidx_record.json"
    )
    url = "https://www.diving-fish.com/api/maimaidxprober/query/player"
    try:
        data = await post_url(
            url,
            data=json.dumps(payload),
            status_code=200,
            headers={"Content-Type": "application/json", "accept": "*/*"},
            fmt="json",
        )
        if use_cache and data:
            with open(cache_dir, "wb") as f:
                f.write(json.dumps(data))
        return data
    except Exception as e:
        if str(e).startswith("400"):
            if "qq" in payload:
                await msg.finish(msg.locale.t("maimai.message.user_unbound.qq"))
            else:
                await msg.finish(msg.locale.t("maimai.message.user_not_found"))
        elif str(e).startswith("403"):
            if "qq" in payload:
                await msg.finish(msg.locale.t("maimai.message.forbidden.eula"))
            else:
                await msg.finish(msg.locale.t("maimai.message.forbidden"))
        else:
            Logger.error(traceback.format_exc())
        if use_cache and os.path.exists(cache_dir):
            try:
                with open(cache_dir, "r", encoding="utf-8") as f:
                    data = json.loads(f.read())
                await msg.send_message(msg.locale.t("maimai.message.use_cache"))
                return data
            except Exception:
                raise e
        else:
            raise e


async def get_song_record(
    msg: Bot.MessageSession,
    payload: dict,
    sid: Union[str, list[str]],
    use_cache: bool = True,
) -> Optional[str]:
    if DEVELOPER_TOKEN:
        mai_cache_path = os.path.join(cache_path, "maimai-record")
        os.makedirs(mai_cache_path, exist_ok=True)
        cache_dir = os.path.join(
            mai_cache_path, f"{msg.target.sender_id.replace("|", "_")}_maimaidx_song_record.json"
        )
        url = "https://www.diving-fish.com/api/maimaidxprober/dev/player/record"
        try:
            payload.update({"music_id": sid})
            data = await post_url(
                url,
                data=json.dumps(payload),
                status_code=200,
                headers={
                    "Content-Type": "application/json",
                    "accept": "*/*",
                    "Developer-Token": DEVELOPER_TOKEN,
                },
                fmt="json",
            )
            if use_cache and data:
                if os.path.exists(cache_dir):
                    with open(cache_dir, "r", encoding="utf-8") as f:
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
            if str(e).startswith("400"):
                raise ConfigValueError("[I18N:error.config.invalid]")
            Logger.error(traceback.format_exc())
            if use_cache and os.path.exists(cache_dir):
                try:
                    with open(cache_dir, "r", encoding="utf-8") as f:
                        data = json.loads(f.read())
                    await msg.send_message(msg.locale.t("maimai.message.use_cache"))
                    return data
                except Exception:
                    raise e
            else:
                raise e
    else:
        raise ConfigValueError("[I18N:error.config.secret.not_found]")


async def get_total_record(
    msg: Bot.MessageSession, payload: dict, utage: bool = False, use_cache: bool = True
):
    mai_cache_path = os.path.join(cache_path, "maimai-record")
    os.makedirs(mai_cache_path, exist_ok=True)
    cache_dir = os.path.join(
        mai_cache_path, f"{msg.target.sender_id.replace("|", "_")}_maimaidx_total_record.json"
    )
    url = "https://www.diving-fish.com/api/maimaidxprober/query/plate"
    payload["version"] = versions
    try:
        data = await post_url(
            url,
            data=json.dumps(payload),
            status_code=200,
            headers={"Content-Type": "application/json", "accept": "*/*"},
            fmt="json",
        )
        if use_cache and data:
            with open(cache_dir, "wb") as f:
                f.write(json.dumps(data))
        if not utage:
            data = {
                "verlist": [d for d in data["verlist"] if d.get("id", 0) < 100000]
            }  # 过滤宴谱
        return data
    except Exception as e:
        if str(e).startswith("400"):
            if "qq" in payload:
                await msg.finish(msg.locale.t("maimai.message.user_unbound.qq"))
            else:
                await msg.finish(msg.locale.t("maimai.message.user_not_found"))
        elif str(e).startswith("403"):
            if "qq" in payload:
                await msg.finish(msg.locale.t("maimai.message.forbidden.eula"))
            else:
                await msg.finish(msg.locale.t("maimai.message.forbidden"))
        else:
            Logger.error(traceback.format_exc())
        if use_cache and os.path.exists(cache_dir):
            try:
                with open(cache_dir, "r", encoding="utf-8") as f:
                    data = json.loads(f.read())
                await msg.send_message(msg.locale.t("maimai.message.use_cache"))
                if not utage:
                    data = {
                        "verlist": [
                            d for d in data["verlist"] if d.get("id", 0) < 100000
                        ]
                    }  # 过滤宴谱
                return data
            except Exception:
                raise e
        else:
            raise e


async def get_plate(
    msg: Bot.MessageSession, payload: dict, version: str, use_cache: bool = True
) -> Optional[str]:
    version = "舞" if version == "覇" else version  # “覇者”属于舞代
    mai_cache_path = os.path.join(cache_path, "maimai-record")
    os.makedirs(mai_cache_path, exist_ok=True)
    cache_dir = os.path.join(
        mai_cache_path, f"{msg.target.sender_id.replace("|", "_")}_maimaidx_plate_{version}.json"
    )
    url = "https://www.diving-fish.com/api/maimaidxprober/query/plate"
    try:
        data = await post_url(
            url,
            data=json.dumps(payload),
            status_code=200,
            headers={"Content-Type": "application/json", "accept": "*/*"},
            fmt="json",
        )
        data = {
            "verlist": [d for d in data["verlist"] if d.get("id", 0) < 100000]
        }  # 过滤宴谱
        if use_cache and data:
            with open(cache_dir, "wb") as f:
                f.write(json.dumps(data))
        return data
    except Exception as e:
        if str(e).startswith("400"):
            if "qq" in payload:
                await msg.finish(msg.locale.t("maimai.message.user_unbound.qq"))
            else:
                await msg.finish(msg.locale.t("maimai.message.user_not_found"))
        elif str(e).startswith("403"):
            if "qq" in payload:
                await msg.finish(msg.locale.t("maimai.message.forbidden.eula"))
            else:
                await msg.finish(msg.locale.t("maimai.message.forbidden"))
        else:
            Logger.error(traceback.format_exc())
        if use_cache and os.path.exists(cache_dir):
            try:
                with open(cache_dir, "r", encoding="utf-8") as f:
                    data = json.loads(f.read())
                await msg.send_message(msg.locale.t("maimai.message.use_cache"))
                return data
            except Exception:
                raise e
        else:
            raise e
