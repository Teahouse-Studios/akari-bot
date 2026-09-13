import time
import unicodedata
from typing import Any

import orjson

from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import ActionText, I18NContext, Image, Plain
from core.constants.exceptions import ConfigValueError
from core.constants.path import cache_path
from core.logger import Logger
from core.utils.http import get_url, download
from .chunithm_mapping import *
from .chunithm_music import Music, TotalList
from .divingfish_oauth import (
    DF_OAUTH_ENABLED,
    DivingFishTokenRevoked,
    request_player_data,
)
from .lxns_oauth import (
    LXNS_API_BASE,
    LXNS_CHUNITHM_PLAYER_URL,
    LXNS_OAUTH_ENABLED,
    LxnsTokenRevoked,
    unwrap,
)
from .lxns_oauth import request_player_data as request_lxns_data
from ..database.models import DivingProberBindInfo, LxnsProberBindInfo
from core.config.base import CoreConfig

DF_CHUNITHM_RECORDS_URL = "https://www.diving-fish.com/api/chunithmprober/player/records"
DF_CHUNITHM_LATEST_VERSION_URL = "https://www.diving-fish.com/api/chunithmprober/latest_version"
LXNS_CHUNITHM_BESTS_URL = f"{LXNS_API_BASE}/user/chunithm/player/bests"

# 新曲版本标识的缓存时长（秒）。
_LATEST_VERSION_CACHE_TTL = 3600
_latest_versions_cache: dict[str, Any] = {"versions": [], "expires": 0.0}

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
                    if CoreConfig.debug:
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


async def get_latest_versions() -> list[str]:
    """获取查分器认定为「新曲」的版本标识，用于区分 B30 与 N20。

    该端点无需验证，且版本标识变动不频繁，故进程内缓存一小时。

    :return: 版本标识列表；获取失败时返回空列表。
    """
    if _latest_versions_cache["expires"] > time.monotonic():
        return _latest_versions_cache["versions"]
    try:
        data = await get_url(DF_CHUNITHM_LATEST_VERSION_URL, status_code=200, fmt="json")
        versions = [str(v) for v in data.get("version", [])]
    except Exception:
        Logger.exception()
        return []
    _latest_versions_cache["versions"] = versions
    _latest_versions_cache["expires"] = time.monotonic() + _LATEST_VERSION_CACHE_TTL
    return versions


def split_chunithm_best(all_best: list[dict], new_best: list[dict]) -> dict:
    """把完整成绩拆分为 B30 与 N20。

    `/player/records` 返回的 `records.best` 是完整的最佳成绩列表，而绘制 B30 所需的两段成绩
    分别为「非最新版本的最佳 30 张」与「最新版本的最佳 20 张」，故须自行拆分：带 `version`
    过滤参数再取一次成绩即得新曲部分，其余即为非新曲部分。

    :param all_best: 完整的最佳成绩列表。
    :param new_best: 仅含最新版本歌曲的成绩列表。
    :return: 含 `b30` 与 `n20` 的成绩字典。
    """
    new_cids = {str(item.get("cid", "")) for item in new_best}
    old_best = [item for item in all_best if str(item.get("cid", "")) not in new_cids]
    return {
        "b30": sorted(old_best, key=lambda x: x.get("ra", 0), reverse=True)[:30],
        "n20": sorted(new_best, key=lambda x: x.get("ra", 0), reverse=True)[:20],
    }


async def get_record_df(
    msg: Bot.MessageSession, bind_info: DivingProberBindInfo, use_cache: bool = True
) -> dict | None:
    """以 OAuth 令牌查询玩家的完整成绩，并整理为 B30 / N20。

    :param msg: 消息会话。
    :param bind_info: 该用户的水鱼绑定记录。
    :param use_cache: 是否读写本地缓存。
    :return: 含 `nickname`、`rating` 与 `records.b30` / `records.n20` 的成绩字典。
    """
    mai_cache_path = cache_path / "maimai-record"
    mai_cache_path.mkdir(parents=True, exist_ok=True)
    cache_dir = mai_cache_path / f"{msg.session_info.sender_id.replace('|', '_')}_chunithm_record_df.json"

    if not DF_OAUTH_ENABLED:
        raise ConfigValueError("{I18N:error.config.secret.not_found}")

    try:
        data = await request_player_data(bind_info, DF_CHUNITHM_RECORDS_URL)
        best: list[dict] = data.get("records", {}).get("best", []) or []
        new_best: list[dict] = []
        versions = await get_latest_versions()
        if versions:
            filtered = await request_player_data(
                bind_info, DF_CHUNITHM_RECORDS_URL, params={"version": ",".join(versions)}
            )
            new_best = filtered.get("records", {}).get("best", []) or []
        data = {
            "nickname": data.get("nickname", ""),
            "rating": data.get("rating", 0),
            "records": split_chunithm_best(best, new_best),
        }
        if use_cache and data:
            with open(cache_dir, "wb") as f:
                f.write(orjson.dumps(data))
        return data
    except Exception as e:
        if isinstance(e, DivingFishTokenRevoked):
            Logger.warning(f"The Diving-Fish authorization of {msg.session_info.sender_id} is no longer valid: {e}")
            await msg.finish(
                I18NContext(
                    "maimai.message.oauth.revoked",
                    cmd=ActionText(f"{msg.session_info.prefixes[0]}chunithm bind df"),
                )
            )
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


async def process_lxdata(profile_data, record_data) -> dict:
    """把落雪的玩家信息与 Best 成绩整理成 B30 与 N20。

    落雪的 `bests` 端点已经分好 B30 与 N20，无需像水鱼那样自行按版本拆分；定数仍取自本地
    曲库，本地缺曲时记 0。

    :param profile_data: 玩家信息响应。
    :param record_data: Best 成绩响应。
    :return: 含 `nickname`、`rating` 与 `records.b30` / `records.n20` 的成绩字典。
    """
    profile = unwrap(profile_data)
    if not isinstance(profile, dict):
        profile = {}
    nickname = unicodedata.normalize("NFKC", profile.get("name", ""))
    rating = profile.get("rating", 0)

    record = unwrap(record_data)
    if not isinstance(record, dict):
        record = {}
    origin_bests = record.get("bests", [])
    origin_new_bests = record.get("new_bests", [])

    new_bests = []
    for item in origin_bests:
        music = (await total_list.get()).by_id(str(item.get("id", "")))
        level_index = item.get("level_index", 0)
        ds = music.ds[level_index] if music and level_index < len(music.ds) else 0
        new_bests.append(
            {
                "mid": item.get("id", ""),
                "title": item.get("song_name", ""),
                "level": item.get("level", ""),
                "level_index": level_index,
                "ds": ds,
                "score": item.get("score", 0),
                "ra": item.get("rating", 0),
                "fc": item.get("full_combo", ""),
            }
        )
    new_new_bests = []
    for item in origin_new_bests:
        music = (await total_list.get()).by_id(str(item.get("id", "")))
        level_index = item.get("level_index", 0)
        ds = music.ds[level_index] if music and level_index < len(music.ds) else 0
        new_new_bests.append(
            {
                "mid": item.get("id", ""),
                "title": item.get("song_name", ""),
                "level": item.get("level", ""),
                "level_index": level_index,
                "ds": ds,
                "score": item.get("score", 0),
                "ra": item.get("rating", 0),
                "fc": item.get("full_combo", ""),
            }
        )

    return {"nickname": nickname, "rating": rating, "records": {"b30": new_bests, "n20": new_new_bests}}


async def get_record_lx(msg: Bot.MessageSession, bind_info, use_cache: bool = True) -> dict | None:
    """取得中二的 B30 / N20 成绩。

    已授权 OAuth 的绑定由令牌决定查询对象；仅有好友码的旧绑定仍走开发者令牌接口。

    :param msg: 消息会话。
    :param bind_info: 落雪绑定记录，或仅有好友码的旧绑定的好友码。
    :param use_cache: 是否读写本地缓存。
    :return: 含 `nickname`、`rating` 与 `records.b30` / `records.n20` 的成绩字典。
    """
    mai_cache_path = cache_path / "maimai-record"
    mai_cache_path.mkdir(parents=True, exist_ok=True)
    cache_dir = mai_cache_path / f"{msg.session_info.sender_id.replace('|', '_')}_chunithm_record_lx.json"

    if isinstance(bind_info, LxnsProberBindInfo) and bind_info.refresh_token:
        return await get_record_lx_oauth(msg, bind_info, cache_dir, use_cache)
    friend_code = bind_info.friend_code if isinstance(bind_info, LxnsProberBindInfo) else bind_info

    if friend_code and LX_DEVELOPER_TOKEN:
        profile_url = f"https://maimai.lxns.net/api/v0/chunithm/player/{friend_code}"
        record_url = f"https://maimai.lxns.net/api/v0/chunithm/player/{friend_code}/bests"
        try:
            profile_data = await get_url(
                profile_url,
                status_code=200,
                headers={
                    "User-Agent": "AkariBot/1.0",
                    "Authorization": LX_DEVELOPER_TOKEN,
                    "Content-Type": "application/json",
                    "accept": "*/*",
                },
                fmt="json",
            )
            record_data = await get_url(
                record_url,
                status_code=200,
                headers={
                    "User-Agent": "AkariBot/1.0",
                    "Authorization": LX_DEVELOPER_TOKEN,
                    "Content-Type": "application/json",
                    "accept": "*/*",
                },
                fmt="json",
            )

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


async def get_record_lx_oauth(
    msg: Bot.MessageSession, bind_info: LxnsProberBindInfo, cache_dir, use_cache: bool = True
) -> dict | None:
    """以 OAuth 令牌取得中二的 B30 / N20。

    :param msg: 消息会话。
    :param bind_info: 该用户的落雪绑定记录。
    :param cache_dir: 缓存文件路径。
    :param use_cache: 是否读写本地缓存。
    :return: 含 `nickname`、`rating` 与 `records.b30` / `records.n20` 的成绩字典。
    """
    if not LXNS_OAUTH_ENABLED:
        raise ConfigValueError("{I18N:error.config.secret.not_found}")
    try:
        profile_data = await request_lxns_data(bind_info, LXNS_CHUNITHM_PLAYER_URL)
        record_data = await request_lxns_data(bind_info, LXNS_CHUNITHM_BESTS_URL)
        data = await process_lxdata(profile_data, record_data)
        if use_cache and data:
            with open(cache_dir, "wb") as f:
                f.write(orjson.dumps(data))
        return data
    except Exception as e:
        if isinstance(e, LxnsTokenRevoked):
            Logger.warning(f"LXNS refresh token is no longer valid: {e}")
            await msg.finish(
                I18NContext(
                    "maimai.message.oauth.lx.revoked",
                    cmd=ActionText(f"{msg.session_info.prefixes[0]}chunithm bind lx"),
                )
            )
        elif str(e).startswith(("400", "404")):
            await msg.finish(I18NContext("maimai.message.user_not_found.lx"))
        elif str(e).startswith("403"):
            await msg.finish(I18NContext("maimai.message.forbidden"))
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
