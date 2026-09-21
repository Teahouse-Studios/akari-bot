from collections import defaultdict

import orjson

from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import ActionText, I18NContext, Image, Plain
from core.constants.exceptions import ConfigValueError
from core.constants.path import cache_path
from core.logger import Logger
from core.utils.func import is_int
from core.utils.http import download, get_url, post_url
from .divingfish_oauth import (
    DF_OAUTH_ENABLED,
    DivingFishTokenRevoked,
    diving_fish_bind_usable,
    request_player_data,
)
from .maimaidx_mapping import *
from .maimaidx_music import get_cover_len5_id, Music, TotalList
from .lxns_apidata import (
    get_plate_lx,
    get_record_lx,
    get_song_record_lx,
    get_total_record_lx,
)
from .source import GAME_MAIMAI, SOURCE_LXNS, pick_source
from ..database.models import DivingProberBindInfo
from core.config.base import CoreConfig

total_list = TotalList()


async def get_bind_info(msg: Bot.MessageSession) -> DivingProberBindInfo:
    bind_info = await DivingProberBindInfo.get_by_sender_id(msg, create=False)
    if not diving_fish_bind_usable(bind_info):
        await msg.finish(
            I18NContext(
                "maimai.message.user_unbound",
                cmd=ActionText(f"{msg.session_info.prefixes[0]}maimai bind df"),
            )
        )
    return bind_info


async def prompt_rebind(msg: Bot.MessageSession, exc: DivingFishTokenRevoked) -> None:
    Logger.warning(f"The Diving-Fish authorization of {msg.session_info.sender_id} is no longer valid: {exc}")
    await msg.finish(
        I18NContext(
            "maimai.message.oauth.revoked",
            cmd=ActionText(f"{msg.session_info.prefixes[0]}maimai bind df"),
        )
    )


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
                    if CoreConfig.debug:
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

            for song in yuzuchan_data.get("content", []):
                song_id = str(song.get("SongID", ""))
                name = song.get("Name", "")
                alias_list = [a for a in song.get("Alias", []) if a.lower() != name.lower()]
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
    info = MessageChain.assign(Plain(f"{music.id} - {music.title}{' (DX)' if music['type'] == 'DX' else ''}"))

    cover_id = str(music.id)
    if int(cover_id) > 100000:
        cover_id = str(cover_id)[2:]
        if music["type"] == "DX":
            cover_id = "1" + str(cover_id)

    cover_path = mai_cover_path / f"{cover_id}.png"
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
            I18NContext(
                "maimai.message.alias.file_not_found",
                cmd=ActionText(f"{msg.session_info.prefixes[0]}maimai update"),
            )
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
    from langconv.converter import LanguageConverter
    from langconv.language.zh import zh_cn

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
    msg: Bot.MessageSession,
    payload: dict | None = None,
    friend_code: str = "",
    use_cache: bool = True,
) -> dict | None:
    """按数据源取回 B50，形状统一为水鱼 `/query/player` 的返回。

    :param msg: 消息会话。
    :param payload: 水鱼查询载荷，含 `qq` 或 `username`。
    :param friend_code: 落雪好友码；查询他人时由调用方给出。
    :param use_cache: 是否读写本地缓存。
    :return: 含 `nickname`、`rating` 与 `charts` 的成绩字典。
    """
    if pick_source(msg, GAME_MAIMAI) == SOURCE_LXNS:
        return await get_record_lx(msg, friend_code=friend_code, use_cache=use_cache)
    payload = payload or {}
    mai_cache_path = cache_path / "maimai-record"
    mai_cache_path.mkdir(parents=True, exist_ok=True)
    cache_dir = mai_cache_path / f"{msg.session_info.sender_id.replace('|', '_')}_maimaidx_record.json"
    url = "https://www.diving-fish.com/api/maimaidxprober/query/player"
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
    sid: str | list[str],
    use_cache: bool = True,
) -> str | None:
    if pick_source(msg, GAME_MAIMAI) == SOURCE_LXNS:
        return await get_song_record_lx(msg, sid, use_cache)
    if DF_OAUTH_ENABLED:
        bind_info = await get_bind_info(msg)
        mai_cache_path = cache_path / "maimai-record"
        mai_cache_path.mkdir(parents=True, exist_ok=True)
        cache_dir = mai_cache_path / f"{msg.session_info.sender_id.replace('|', '_')}_maimaidx_song_record.json"
        url = "https://www.diving-fish.com/api/maimaidxprober/player/record"
        try:
            data = await request_player_data(bind_info, url, method="POST", data={"music_id": sid})
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
            if isinstance(e, DivingFishTokenRevoked):
                await prompt_rebind(msg, e)
            elif str(e).startswith("400"):
                raise ConfigValueError("{I18N:error.config.invalid}")
            elif str(e).startswith("429"):
                await msg.send_message(I18NContext("maimai.message.oauth.rate_limit"))
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


async def get_total_record(
    msg: Bot.MessageSession,
    utage: bool = False,
    use_cache: bool = True,
):
    if pick_source(msg, GAME_MAIMAI) == SOURCE_LXNS:
        return await get_total_record_lx(msg, utage, use_cache)
    if DF_OAUTH_ENABLED:
        bind_info = await get_bind_info(msg)
        mai_cache_path = cache_path / "maimai-record"
        mai_cache_path.mkdir(parents=True, exist_ok=True)
        cache_dir = mai_cache_path / f"{msg.session_info.sender_id.replace('|', '_')}_maimaidx_total_record.json"
        url = "https://www.diving-fish.com/api/maimaidxprober/player/records"
        try:
            data = await request_player_data(bind_info, url)
            if use_cache and data:
                with open(cache_dir, "wb") as f:
                    f.write(orjson.dumps(data))
            if not utage:
                data = {"records": [d for d in data.get("records", []) if int(d.get("id", 0)) < 100000]}  # 过滤宴谱
            return data
        except Exception as e:
            if isinstance(e, DivingFishTokenRevoked):
                await prompt_rebind(msg, e)
            elif str(e).startswith("400"):
                await msg.finish(I18NContext("maimai.message.user_not_found.df"))
            elif str(e).startswith("403"):
                await msg.finish(I18NContext("maimai.message.forbidden.eula"))
            elif str(e).startswith("429"):
                await msg.send_message(I18NContext("maimai.message.oauth.rate_limit"))
            else:
                Logger.exception()
            if use_cache and cache_dir.exists():
                try:
                    with open(cache_dir, "rb") as f:
                        data = orjson.loads(f.read())
                    await msg.send_message(I18NContext("maimai.message.use_cache"))
                    if not utage:
                        data = {"records": [d for d in data.get("records", []) if d.get("id", 0) < 100000]}  # 过滤宴谱
                    return data
                except Exception:
                    raise e
            else:
                raise e
    else:
        raise ConfigValueError("{I18N:error.config.secret.not_found}")


async def get_plate(msg: Bot.MessageSession, payload: dict, version: str, use_cache: bool = True) -> dict | None:
    if pick_source(msg, GAME_MAIMAI) == SOURCE_LXNS:
        return await get_plate_lx(msg, payload, version, use_cache)
    # OAuth 下查询对象由令牌决定，此处的载荷只用于携带版本列表。
    if DF_OAUTH_ENABLED:
        bind_info = await get_bind_info(msg)
        version = "舞" if version == "覇" else version  # “覇者”属于舞代
        mai_cache_path = cache_path / "maimai-record"
        mai_cache_path.mkdir(parents=True, exist_ok=True)
        cache_dir = mai_cache_path / f"{msg.session_info.sender_id.replace('|', '_')}_maimaidx_plate_{version}.json"
        url = "https://www.diving-fish.com/api/maimaidxprober/player/plate"
        try:
            data = await request_player_data(
                bind_info, url, method="POST", data={"version": payload.get("version", [])}
            )
            data = {"verlist": [d for d in data.get("verlist", []) if int(d.get("id", 0)) < 100000]}  # 过滤宴谱
            if use_cache and data:
                with open(cache_dir, "wb") as f:
                    f.write(orjson.dumps(data))
            return data
        except Exception as e:
            if isinstance(e, DivingFishTokenRevoked):
                await prompt_rebind(msg, e)
            elif str(e).startswith("400"):
                await msg.finish(I18NContext("maimai.message.user_not_found.df"))
            elif str(e).startswith("403"):
                await msg.finish(I18NContext("maimai.message.forbidden.eula"))
            elif str(e).startswith("429"):
                await msg.send_message(I18NContext("maimai.message.oauth.rate_limit"))
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
