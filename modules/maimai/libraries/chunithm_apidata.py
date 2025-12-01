from typing import Optional
import unicodedata

import orjson

from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import I18NContext, Image, Plain
from core.constants.exceptions import ConfigValueError
from core.constants.path import cache_path
from core.logger import Logger
from core.utils.http import get_url, post_url, download
from .chunithm_mapping import *
from .chunithm_music import Music, TotalList

total_list = TotalList()


async def update_cover() -> bool:
    id_list = []
    for song in await total_list.get():
        id_list.append(song["id"])
    chu_cover_path.mkdir(parents=True, exist_ok=True)
    for id in id_list:
        cover_path = chu_cover_path / f"{id}.png"
        if not cover_path.exists():
            try:
                url = f"https://lxns.org/chunithm/jacket/{id}.png"
                await download(
                    url,
                    status_code=200,
                    path=chu_cover_path,
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
                Logger.exception()
                return False
    return True


async def get_info(music: Music, details) -> MessageChain:
    info = MessageChain.assign(Plain(f"{music.id} - {music.title}"))
    cover_path = chu_cover_path / f"{music.id}.png"
    if cover_path.exists():
        info.append(Image(cover_path))
    if details:
        if not isinstance(details, MessageChain):
            details = MessageChain.assign(details)
        info += details

    return info


async def get_record_df(
    msg: Bot.MessageSession, payload: dict, use_cache: bool = True
) -> Optional[dict]:
    mai_cache_path = cache_path / "maimai-record"
    mai_cache_path.mkdir(parents=True, exist_ok=True)
    cache_dir = mai_cache_path / f"{msg.session_info.sender_id.replace("|", "_")}_chunithm_record_df.json"
    url = "https://www.diving-fish.com/api/chunithmprober/query/player"
    try:
        data = await post_url(
            url,
            data=orjson.dumps(payload),
            status_code=200,
            headers={"Content-Type": "application/json", "accept": "*/*"},
            fmt="json"
        )
        if use_cache and data:
            with open(cache_dir, "wb") as f:
                f.write(orjson.dumps(data))
        return data
    except Exception as e:
        if str(e).startswith("400"):
            if "qq" in payload:
                await msg.finish(I18NContext("maimai.message.user_unbound.qq"))
            else:
                await msg.finish(I18NContext("maimai.message.user_not_found.df"))
        elif str(e).startswith("403"):
            if "qq" in payload:
                await msg.finish(I18NContext("maimai.message.forbidden.eula"))
            else:
                await msg.finish(I18NContext("maimai.message.forbidden"))
        else:
            Logger.exception()
        if use_cache and cache_dir.exists():
            try:
                with open(cache_dir, "rb") as f:
                    data = orjson.loads(f.read())
                await msg.send_message(I18NContext("maimai.message.use_cache"))
                return data
            except Exception:
                raise e
        else:
            raise e


async def get_record_lx(
    msg: Bot.MessageSession, friend_code: str, use_cache: bool = True
) -> Optional[dict]:
    mai_cache_path = cache_path / "maimai-record"
    mai_cache_path.mkdir(parents=True, exist_ok=True)
    cache_dir = mai_cache_path / f"{msg.session_info.sender_id.replace("|", "_")}_chunithm_record_lx.json"

    if LX_DEVELOPER_TOKEN:
        profile_url = f"https://maimai.lxns.net/api/v0/chunithm/player/{friend_code}"
        record_url = f"https://maimai.lxns.net/api/v0/chunithm/player/{friend_code}/bests"
        try:
            profile_data = await get_url(
                profile_url,
                status_code=200,
                headers={"User-Agent": "AkariBot/1.0", "Authorization": LX_DEVELOPER_TOKEN, "Content-Type": "application/json", "accept": "*/*"},
                fmt="json"
            )
            record_data = await get_url(
                record_url,
                status_code=200,
                headers={"User-Agent": "AkariBot/1.0", "Authorization": LX_DEVELOPER_TOKEN, "Content-Type": "application/json", "accept": "*/*"},
                fmt="json"
            )

            async def process_lxdata(profile_data, record_data):
                nickname = unicodedata.normalize("NFKC", profile_data["data"]["name"])
                rating = profile_data["data"]["rating"]

                record = record_data["data"]
                origin_bests = record["bests"]
                origin_new_bests = record["new_bests"]

                new_bests = []
                for item in origin_bests:
                    music = (await total_list.get()).by_id(item["id"])
                    new_bests.append({
                        "mid": item["id"],
                        "title": item["song_name"],
                        "level": item["level"],
                        "level_index": item["level_index"],
                        "ds": music.ds[item["level_index"]],
                        "score": item["score"],
                        "ra": item["rating"],
                        "fc": item["full_combo"],
                    })
                new_new_bests = []
                for item in origin_new_bests:
                    music = (await total_list.get()).by_id(item["id"])
                    new_new_bests.append({
                        "mid": item["id"],
                        "title": item["song_name"],
                        "level": item["level"],
                        "level_index": item["level_index"],
                        "ds": music.ds[item["level_index"]],
                        "score": item["score"],
                        "ra": item["rating"],
                        "fc": item["full_combo"],
                    })

                return {
                    "nickname": nickname,
                    "rating": rating,
                    "records": {
                        "b30": new_bests,
                        "n20": new_new_bests
                    }
                }

            data = await process_lxdata(profile_data, record_data)
            if use_cache and data:
                with open(cache_dir, "wb") as f:
                    f.write(orjson.dumps(data))
            return data
        except Exception as e:
            if str(e).startswith(("400", "404")):
                await msg.finish(I18NContext("maimai.message.user_not_found.lx"))
            elif str(e).startswith("401"):
                raise ConfigValueError("{I18N:error.config.invalid}")
            elif str(e).startswith("403"):
                await msg.finish(I18NContext("maimai.message.forbidden"))
            else:
                Logger.exception()
            if use_cache and cache_dir.exists():
                try:
                    with open(cache_dir, "rb") as f:
                        data = orjson.loads(f.read())
                    await msg.send_message(I18NContext("maimai.message.use_cache"))
                    return data
                except Exception:
                    raise e
            else:
                raise e
    else:
        raise ConfigValueError("{I18N:error.config.secret.not_found}")
