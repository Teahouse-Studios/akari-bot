from collections import defaultdict

import orjson
from langconv.converter import LanguageConverter
from langconv.language.zh import zh_cn

from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import I18NContext, Image, Plain
from core.config import Config
from core.constants.exceptions import ConfigValueError
from core.constants.path import cache_path
from core.logger import Logger
from core.utils.http import download, get_url, post_url
from core.utils.tools import is_int
from .maimaidx_mapping import *
from .maimaidx_music import get_cover_len5_id, Music, TotalList

total_list = TotalList()


async def update_cover() -> bool:
    id_list = ["0", "1000"]
    for song in await total_list.get():
        id_list.append(song["id"])
    mai_cover_path.mkdir(parents=True, exist_ok=True)
    for id in id_list:
        cover_path = mai_cover_path / f"{id}.png"
        if not cover_path.exists():
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
                Logger.exception()
                return False
    return True


async def update_alias() -> bool:
    try:
        alias_map = defaultdict(lambda: {"song_id": "", "name": "", "alias": set()})
        try:
            yuzuchan_data = await get_url("https://www.yuzuchan.moe/api/maimaidx/maimaidxalias", 200, fmt="json")

            for song in yuzuchan_data["content"]:
                song_id = str(song["SongID"])
                name = song["Name"]
                alias_list = [a for a in song["Alias"] if a.lower() != name.lower()]
                alias_map[song_id]["song_id"] = song_id
                alias_map[song_id]["name"] = name
                alias_map[song_id]["alias"].update(alias_list)

        except Exception:
            Logger.exception()
        if not alias_map:
            return False

        alias_data = []
        for song_id, info in alias_map.items():
            fmt_data = {"song_id": song_id}
            if info.get("name"):
                fmt_data["name"] = info["name"]
                fmt_data["alias"] = [a for a in info["alias"] if a.lower() != info["name"].lower()]
            else:
                fmt_data["alias"] = list(info["alias"])

            alias_data.append(fmt_data)

        with open(mai_alias_path, "wb") as file:
            file.write(orjson.dumps(alias_data, option=orjson.OPT_INDENT_2))

        return True
    except Exception:
        Logger.exception()
        return False


async def get_info(music: Music, details: str | MessageChain) -> MessageChain:
    info = MessageChain.assign(Plain(f"{music.id} - {music.title}{" (DX)" if music["type"] == "DX" else ""}"))
    cover_path = mai_cover_path / f"{music.id}.png"
    if cover_path.exists():
        info.append(Image(cover_path))
    else:
        cover_path = mai_cover_path / "0.png"
        if cover_path.exists():
            info.append(Image(cover_path))
    if details:
        if not isinstance(details, MessageChain):
            details = MessageChain.assign(details)
        info += details

    return info


async def get_alias(msg: Bot.MessageSession, sid: str) -> list:
    if not mai_alias_path.exists():
        await msg.finish(
            I18NContext("maimai.message.alias.file_not_found", prefix=msg.session_info.prefixes[0])
        )
    with open(mai_alias_path, "rb") as file:
        data = orjson.loads(file.read())

    result = []
    for song in data:
        if str(song["song_id"]) == sid:
            result = sorted(song["alias"])  # 此处的列表是歌曲别名列表
            break

    return result


async def search_by_alias(input_: str) -> list:
    result = []
    convinput = LanguageConverter.from_language(zh_cn).convert(input_)

    res = (await total_list.get()).filter(title=input_)
    for s in res:
        result.append(s["id"])

    if is_int(input_):
        music = (await total_list.get()).by_id(input_)
        if music:
            result.append(input_)

    if not mai_alias_path.exists():
        return list(set(result))

    with open(mai_alias_path, "rb") as file:
        data = orjson.loads(file.read())

    for song in data:
        aliases = [alias.lower() for alias in song["alias"]]
        if input_.lower() in aliases or convinput.lower() in aliases:
            result.append(str(song["song_id"]))  # 此处的列表是歌曲 ID 列表

    return list(set(result))


async def get_record(
    msg: Bot.MessageSession, payload: dict, use_cache: bool = True
) -> dict | None:
    mai_cache_path = cache_path / "maimai-record"
    mai_cache_path.mkdir(parents=True, exist_ok=True)
    cache_dir = mai_cache_path / f"{msg.session_info.sender_id.replace("|", "_")}_maimaidx_record.json"
    url = "https://www.diving-fish.com/api/maimaidxprober/query/player"
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


async def get_song_record(
    msg: Bot.MessageSession,
    payload: dict,
    sid: str | list[str],
    use_cache: bool = True,
) -> str | None:
    if DF_DEVELOPER_TOKEN:
        mai_cache_path = cache_path / "maimai-record"
        mai_cache_path.mkdir(parents=True, exist_ok=True)
        cache_dir = mai_cache_path / f"{msg.session_info.sender_id.replace("|", "_")}_maimaidx_song_record.json"
        url = "https://www.diving-fish.com/api/maimaidxprober/dev/player/record"
        try:
            payload.update({"music_id": sid})
            data = await post_url(
                url,
                data=orjson.dumps(payload),
                status_code=200,
                headers={
                    "Content-Type": "application/json",
                    "accept": "*/*",
                    "Developer-Token": DF_DEVELOPER_TOKEN,
                },
                fmt="json",
            )
            if use_cache and data:
                if cache_dir.exists():
                    with open(cache_dir, "rb") as f:
                        try:
                            backup_data = orjson.loads(f.read())
                        except Exception:
                            backup_data = {}
                else:
                    backup_data = {}
                backup_data.update(data)
                with open(cache_dir, "wb") as f:
                    f.write(orjson.dumps(backup_data))
            return data
        except Exception as e:
            if str(e).startswith("400"):
                raise ConfigValueError("{I18N:error.config.invalid}")
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


async def get_total_record(
    msg: Bot.MessageSession, payload: dict, utage: bool = False, use_cache: bool = True
):
    mai_cache_path = cache_path / "maimai-record"
    mai_cache_path.mkdir(parents=True, exist_ok=True)
    cache_dir = mai_cache_path / f"{msg.session_info.sender_id.replace("|", "_")}_maimaidx_total_record.json"
    url = "https://www.diving-fish.com/api/maimaidxprober/query/plate"
    payload["version"] = versions
    try:
        data = await post_url(
            url,
            data=orjson.dumps(payload),
            status_code=200,
            headers={"Content-Type": "application/json", "accept": "*/*"},
            fmt="json",
        )
        if use_cache and data:
            with open(cache_dir, "wb") as f:
                f.write(orjson.dumps(data))
        if not utage:
            data = {
                "verlist": [d for d in data["verlist"] if int(d.get("id", 0)) < 100000]
            }  # 过滤宴谱
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
) -> dict | None:
    version = "舞" if version == "覇" else version  # “覇者”属于舞代
    mai_cache_path = cache_path / "maimai-record"
    mai_cache_path.mkdir(parents=True, exist_ok=True)
    cache_dir = mai_cache_path / f"{msg.session_info.sender_id.replace("|", "_")}_maimaidx_plate_{version}.json"
    url = "https://www.diving-fish.com/api/maimaidxprober/query/plate"
    try:
        data = await post_url(
            url,
            data=orjson.dumps(payload),
            status_code=200,
            headers={"Content-Type": "application/json", "accept": "*/*"},
            fmt="json",
        )
        data = {
            "verlist": [d for d in data["verlist"] if int(d.get("id", 0)) < 100000]
        }  # 过滤宴谱
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
