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
from core.utils.http import get_url, post_url, download
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
    LXNS_DEVELOPER_ENABLED,
    LXNS_OAUTH_ENABLED,
    LxnsTokenRevoked,
    fetch_player_field,
    request_developer_data,
    unwrap,
)
from .lxns_oauth import request_player_data as request_lxns_data
from ..database.models import DivingProberBindInfo, LxnsProberBindInfo
from core.config.base import CoreConfig

DF_CHUNITHM_RECORDS_URL = "https://www.diving-fish.com/api/chunithmprober/player/records"
DF_CHUNITHM_QUERY_URL = "https://www.diving-fish.com/api/chunithmprober/query/player"
DF_CHUNITHM_LATEST_VERSION_URL = "https://www.diving-fish.com/api/chunithmprober/latest_version"
LXNS_CHUNITHM_BESTS_URL = f"{LXNS_API_BASE}/user/chunithm/player/bests"

# 开发者端点按好友码寻址，能查询任意玩家；好友码相同即同一账号，故查询自己与他人走同一条路。
LXNS_CHUNITHM_PLAYER_BY_FRIEND_CODE_URL = f"{LXNS_API_BASE}/chunithm/player/{{friend_code}}"
LXNS_CHUNITHM_BESTS_BY_FRIEND_CODE_URL = f"{LXNS_API_BASE}/chunithm/player/{{friend_code}}/bests"

# 水鱼的成绩只给难度标级，而绘图按难度序号取色，故按标级补一个序号；标级无法识别时记 0。
_DF_LEVEL_INDEX = {label.lower(): index for index, label in enumerate(diff_list)}

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


def _cache_file(msg: Bot.MessageSession, name: str):
    """给出该用户的缓存文件路径。"""
    cache_dir = cache_path / "maimai-record"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{msg.session_info.sender_id.replace('|', '_')}_{name}.json"


def map_df_chunithm_record(item: dict) -> dict:
    """把水鱼查询端点的成绩换算成绘图所读的形状。

    水鱼的公开端点给出的是难度标级（如 `Master`）而非难度序号，而绘图按序号取色，故缺序号
    时按标级补上；曲名、定数与单曲 Rating 端点都已给全，无需再查本地曲库。

    :param item: 水鱼公开端点给出的成绩。
    :return: 含 `mid`、`title`、`level`、`level_index`、`ds`、`score`、`ra` 与 `fc` 的成绩。
    """
    level_label = str(item.get("level_label") or "").strip().lower()
    level_index = item.get("level_index")
    if level_index is None:
        level_index = _DF_LEVEL_INDEX.get(level_label, 0)
    return {
        "mid": item.get("mid") or item.get("id") or "",
        "title": item.get("title", ""),
        "level": item.get("level", "") or item.get("level_label", ""),
        "level_index": int(level_index),
        "ds": item.get("ds", 0),
        "score": item.get("score", 0),
        "ra": item.get("ra", 0),
        "fc": item.get("fc", ""),
    }


async def get_record_df_by_token(bind_info: DivingProberBindInfo) -> dict:
    """以 OAuth 令牌查询绑定账号的完整成绩，并整理为 B30 / N20。

    带 `version` 过滤参数再取一次成绩即得新曲部分，其余即为非新曲部分。

    :param bind_info: 该用户的水鱼绑定记录。
    :return: 含 `nickname`、`rating` 与 `records.b30` / `records.n20` 的成绩字典。
    """
    data = await request_player_data(bind_info, DF_CHUNITHM_RECORDS_URL)
    best: list[dict] = (data.get("records") or {}).get("best") or []
    new_best: list[dict] = []
    versions = await get_latest_versions()
    if versions:
        filtered = await request_player_data(bind_info, DF_CHUNITHM_RECORDS_URL, params={"version": ",".join(versions)})
        new_best = (filtered.get("records") or {}).get("best") or []
    return {
        "nickname": data.get("nickname", ""),
        "rating": data.get("rating", 0),
        "records": split_chunithm_best(best, new_best),
    }


async def get_record_df_by_username(username: str) -> dict:
    """按用户名查询公开端点，并整理为 B30 / N20。

    水鱼把两段成绩分好之后再返回，无需像 OAuth 端点那样自行按版本拆分；成绩里的难度只给出
    标级，故逐条换算成绘图所读的形状。

    :param username: 水鱼用户名。
    :return: 含 `nickname`、`rating` 与 `records.b30` / `records.n20` 的成绩字典。
    """
    data = await post_url(
        DF_CHUNITHM_QUERY_URL,
        data=orjson.dumps({"username": username}),
        status_code=200,
        headers={"Content-Type": "application/json", "accept": "*/*"},
        fmt="json",
    )
    records = data.get("records") or {}
    return {
        # 该端点把玩家名记在 `username` 下，与 OAuth 端点的 `nickname` 不同。
        "nickname": data.get("nickname") or data.get("username", ""),
        "rating": data.get("rating", 0),
        "records": {
            "b30": [map_df_chunithm_record(item) for item in (records.get("b30") or records.get("best") or [])],
            "n20": [map_df_chunithm_record(item) for item in (records.get("n20") or records.get("r10") or [])],
        },
    }


async def get_record_df(
    msg: Bot.MessageSession,
    bind_info: DivingProberBindInfo | None = None,
    username: str = "",
    use_cache: bool = True,
) -> dict | None:
    """取得中二的 B30 / N20。

    查询对象按参数决定：给出用户名时走公开的按用户名查询端点——OAuth 端点只认令牌对应的
    用户，查不了他人；否则以 OAuth 令牌查询绑定账号。按用户名查到的成绩属于他人，与这位
    用户自己写在缓存里的成绩并非同一份，故一概不读写缓存。

    :param msg: 消息会话。
    :param bind_info: 该用户的水鱼绑定记录；按用户名查询时无需给出。
    :param username: 要查询的水鱼用户名；为空时查询绑定账号。
    :param use_cache: 是否读写本地缓存。
    :return: 含 `nickname`、`rating` 与 `records.b30` / `records.n20` 的成绩字典。
    """
    cache_dir = _cache_file(msg, "chunithm_record_df")
    if username:
        # 按用户名查到的成绩属于他人，与这位用户自己写在缓存里的成绩并非同一份，故不读写缓存。
        use_cache = False
    elif not DF_OAUTH_ENABLED:
        # 查询绑定账号必须要有 OAuth 应用；按用户名查询走的是公开端点，不需要授权。
        raise ConfigValueError("{I18N:error.config.secret.not_found}")

    async def fetch():
        if username:
            return await get_record_df_by_username(username)
        return await get_record_df_by_token(bind_info)

    try:
        data = await fetch()
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
            # 查他人时 403 只会是对方的隐私设置，只有查自己才牵扯到用户协议。
            await msg.finish(I18NContext("maimai.message.forbidden" if username else "maimai.message.forbidden.eula"))
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


async def get_record_lx(
    msg: Bot.MessageSession,
    bind_info: LxnsProberBindInfo | None = None,
    friend_code: str = "",
    use_cache: bool = True,
) -> dict | None:
    """取得中二的 B30 / N20。

    查询对象按参数决定：给出好友码时查询该玩家，只有开发者密钥能识别好友码；否则查询令牌
    所属的账号——落雪的令牌认不出好友码，故再用个人资料里的好友码换成开发者端点。

    :param msg: 消息会话。
    :param bind_info: 该用户的落雪绑定记录；按好友码查询时无需给出。
    :param friend_code: 要查询的好友码；为空时查询绑定账号。
    :param use_cache: 是否读写本地缓存。
    :return: 含 `nickname`、`rating` 与 `records.b30` / `records.n20` 的成绩字典。
    """
    if friend_code:
        return await get_record_lx_dev(msg, friend_code, use_cache)
    if not bind_info or not bind_info.refresh_token:
        raise ConfigValueError("{I18N:error.config.secret.not_found}")
    if LXNS_DEVELOPER_ENABLED:
        own_code = await fetch_player_field(bind_info, "friend_code", LXNS_CHUNITHM_PLAYER_URL)
        if own_code:
            return await get_record_lx_dev(msg, own_code, use_cache)
    return await get_record_lx_oauth(msg, bind_info, use_cache)


async def get_record_lx_dev(msg: Bot.MessageSession, friend_code: str, use_cache: bool = True) -> dict | None:
    """以开发者端点按好友码取得中二的 B30 / N20。

    落雪给出的正是游戏内 Rating 所取的三段成绩（旧曲 Best 30、当前版本 Best 20 与 Selection
    10），故配置了开发者密钥便一律走这里。

    :param msg: 消息会话。
    :param friend_code: 落雪好友码。
    :param use_cache: 是否读写本地缓存。
    :return: 含 `nickname`、`rating` 与 `records.b30` / `records.n20` 的成绩字典。
    """
    if not LXNS_DEVELOPER_ENABLED:
        raise ConfigValueError("{I18N:error.config.secret.not_found}")

    async def fetch():
        profile_data = await request_developer_data(
            LXNS_CHUNITHM_PLAYER_BY_FRIEND_CODE_URL.format(friend_code=friend_code)
        )
        record_data = await request_developer_data(
            LXNS_CHUNITHM_BESTS_BY_FRIEND_CODE_URL.format(friend_code=friend_code)
        )
        return await process_lxdata(profile_data, record_data)

    return await _request_lxns_record(msg, fetch, _cache_file(msg, f"chunithm_bests_lx_{friend_code}"), use_cache)


async def get_record_lx_oauth(
    msg: Bot.MessageSession, bind_info: LxnsProberBindInfo, use_cache: bool = True
) -> dict | None:
    """以 OAuth 令牌取得中二的 B30 / N20。

    落雪文档里真正的 Best 是按好友码寻址的开发者端点，故这里只是未配置开发者密钥时的退路。

    :param msg: 消息会话。
    :param bind_info: 该用户的落雪绑定记录。
    :param use_cache: 是否读写本地缓存。
    :return: 含 `nickname`、`rating` 与 `records.b30` / `records.n20` 的成绩字典。
    """
    if not LXNS_OAUTH_ENABLED:
        raise ConfigValueError("{I18N:error.config.secret.not_found}")

    async def fetch():
        profile_data = await request_lxns_data(bind_info, LXNS_CHUNITHM_PLAYER_URL)
        record_data = await request_lxns_data(bind_info, LXNS_CHUNITHM_BESTS_URL)
        return await process_lxdata(profile_data, record_data)

    return await _request_lxns_record(msg, fetch, _cache_file(msg, "chunithm_record_lx"), use_cache)


async def _request_lxns_record(msg: Bot.MessageSession, fetch, cache_dir, use_cache: bool = True) -> dict | None:
    """执行一次落雪取数：成功则写缓存，失败则按错误类型提示并退回本地缓存。

    :param msg: 消息会话。
    :param fetch: 无参协程函数，返回成绩字典。
    :param cache_dir: 缓存文件路径。
    :param use_cache: 是否读写本地缓存。
    :return: 取回的成绩字典或缓存中的成绩字典。
    """
    try:
        data = await fetch()
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
