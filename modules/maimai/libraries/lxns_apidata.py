"""落雪咖啡屋（LXNS）舞萌成绩的适配层。

落雪给出的成绩字段名与曲目 ID 都和水鱼不同，而绘图、列表、名牌板等消费方一律按水鱼的数据
形状读取（`song_id`、`dxScore`、`fc`、`fs`……），故在此统一换算，下游不必关心数据来自哪一侧。
"""

from typing import Any

import orjson

from core.builtins.bot import Bot
from core.builtins.message.internal import ActionText, I18NContext
from core.constants.exceptions import ConfigValueError
from core.constants.path import cache_path
from core.logger import Logger
from .lxns_oauth import (
    LXNS_API_BASE,
    LXNS_MAIMAI_PLAYER_URL,
    LXNS_OAUTH_ENABLED,
    LxnsTokenRevoked,
    request_player_data,
    unwrap,
)
from .maimaidx_mapping import plate_mapping, sd_plate_mapping
from .maimaidx_music import TotalList
from ..database.models import LxnsProberBindInfo

LXNS_MAIMAI_BESTS_URL = f"{LXNS_API_BASE}/user/maimai/player/bests"
LXNS_MAIMAI_SCORES_URL = f"{LXNS_API_BASE}/user/maimai/player/scores"

# 落雪把标准与 DX 谱面记在同一个曲目 ID 下，水鱼则给 DX 谱面的 ID 加 10000，互换即是在
# 这个偏移量上加减。宴会场曲目（ID 大于等于 100000）不分谱面类型，不参与换算。
MAIMAI_DX_ID_OFFSET = 10000
MAIMAI_UTAGE_ID_MIN = 100000

# 落雪的谱面类型到水鱼展示用类型的映射；宴会场曲目不分谱面类型，按标准谱面处理。
_CHART_TYPE_DF = {"standard": "SD", "dx": "DX", "utage": "SD"}

total_list = TotalList()


def lxns_to_df_id(song_id: Any, chart_type: str | None = None) -> str:
    """把落雪曲目 ID 换算成水鱼风格的 ID。

    :param song_id: 落雪曲目 ID。
    :param chart_type: 谱面类型，`standard` 或 `dx`。
    :return: 水鱼风格的曲目 ID；无法解析时返回空字符串。
    """
    try:
        sid = int(song_id)
    except (TypeError, ValueError):
        return ""
    if sid >= MAIMAI_UTAGE_ID_MIN:
        return str(sid)
    if chart_type == "dx":
        sid += MAIMAI_DX_ID_OFFSET
    return str(sid)


def df_to_lxns_id(song_id: Any) -> str:
    """把水鱼风格的曲目 ID 换算回落雪曲目 ID。

    :param song_id: 水鱼风格的曲目 ID。
    :return: 落雪曲目 ID；无法解析时返回空字符串。
    """
    try:
        sid = int(song_id)
    except (TypeError, ValueError):
        return ""
    if is_dx_id(sid):
        sid -= MAIMAI_DX_ID_OFFSET
    return str(sid)


def is_dx_id(song_id: Any) -> bool:
    """判断水鱼风格的曲目 ID 是否指向 DX 谱面。

    :param song_id: 水鱼风格的曲目 ID。
    :return: 是否属于 DX 谱面。
    """
    try:
        sid = int(song_id)
    except (TypeError, ValueError):
        return False
    return MAIMAI_DX_ID_OFFSET <= sid < MAIMAI_UTAGE_ID_MIN


def score_rating(score: dict, ds: float) -> int:
    """取单曲 Rating。

    接口给出 `dx_rating` 时直接采用；缺失时按定数与达成率就地推算，以免排序时把成绩一律
    当作 0 分。本地缺曲便没有定数，只能记 0。

    :param score: 落雪成绩。
    :param ds: 该谱面的定数。
    :return: 单曲 Rating。
    """
    rating = score.get("dx_rating")
    if rating is not None:
        return int(rating)
    if not ds:
        return 0
    from .maimaidx_utils import compute_rating

    return compute_rating(ds, float(score.get("achievements") or 0))


def map_score(score: dict, music: Any = None) -> dict:
    """把一条落雪成绩换算成水鱼形状。

    舞萌的 `Score` 里没有定数，定数只能取自本地曲库；本地缺曲时定数记 0，曲名退回接口给的
    `song_name`，封面的查找也会落空。

    :param score: 落雪成绩。
    :param music: 本地曲库中对应的曲目，可为空。
    :return: 水鱼形状的成绩。
    """
    level_index = int(score.get("level_index") or 0)
    ds = 0.0
    if music and level_index < len(music.get("ds", [])):
        ds = float(music.get("ds", [])[level_index])
    title = score.get("song_name") or (music.get("title", "") if music else "")
    return {
        "song_id": lxns_to_df_id(score.get("id"), score.get("type")),
        "title": title,
        "type": _CHART_TYPE_DF.get(str(score.get("type", "")), "SD"),
        "level": score.get("level", ""),
        "level_index": level_index,
        "ds": ds,
        "achievements": float(score.get("achievements") or 0),
        "fc": score.get("fc") or "",
        "fs": score.get("fs") or "",
        "dxScore": int(score.get("dx_score") or 0),
        "rate": score.get("rate") or "",
        "ra": score_rating(score, ds),
    }


def top_rated(records: list[dict], count: int) -> list[dict]:
    """按单曲 Rating 取前若干条成绩。

    :param records: 水鱼形状的成绩列表。
    :param count: 取前多少条。
    :return: 排序后的成绩列表。
    """
    return sorted(records, key=lambda record: record.get("ra", 0), reverse=True)[:count]


def plate_versions(version: str) -> list[str]:
    """给出版本标识对应的查分器版本名，用于名牌板筛选。

    与名牌板流程保持一致：真代为无印版本，霸者与舞牌取全部标准谱面版本；“初”不是版本名，
    其余按名牌板映射查表。

    :param version: 名牌板的版本标识，如 `舞`、`真`。
    :return: 版本名列表；无法识别时为空列表。
    """
    if version == "真":
        return ["maimai", "maimai PLUS"]
    if version in ("覇", "舞"):
        return list(set(sd_plate_mapping.values()))
    if version in plate_mapping and version != "初":
        return [plate_mapping[version]]
    return []


def _rebind_cmd(msg: Bot.MessageSession) -> ActionText:
    """给出重新绑定落雪账号的命令，供令牌失效时提示。"""
    return ActionText(f"{msg.session_info.prefixes[0]}maimai bind lx")


def _cache_file(msg: Bot.MessageSession, name: str):
    """给出该用户的缓存文件路径。"""
    cache_dir = cache_path / "maimai-record"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{msg.session_info.sender_id.replace('|', '_')}_{name}.json"


async def get_bind_info(msg: Bot.MessageSession) -> LxnsProberBindInfo:
    """取得该用户的落雪绑定记录。

    查询对象由令牌决定，故必须存在这位用户自己的授权记录。

    :param msg: 消息会话。
    :return: 该用户的绑定记录。
    """
    bind_info = await LxnsProberBindInfo.get_by_sender_id(msg, create=False)
    if not bind_info or not bind_info.refresh_token:
        await msg.finish(
            I18NContext(
                "maimai.message.user_unbound",
                cmd=ActionText(f"{msg.session_info.prefixes[0]}maimai bind lx"),
            )
        )
    return bind_info


async def _prompt_error(msg: Bot.MessageSession, e: Exception) -> None:
    """按错误类型给出提示；无法解释的错误只记日志。

    :param msg: 消息会话。
    :param e: 请求抛出的异常。
    """
    if isinstance(e, LxnsTokenRevoked):
        Logger.warning(f"LXNS refresh token is no longer valid: {e}")
        await msg.finish(I18NContext("maimai.message.oauth.lx.revoked", cmd=_rebind_cmd(msg)))
    if str(e).startswith(("400", "404")):
        await msg.finish(I18NContext("maimai.message.user_not_found.lx"))
    if str(e).startswith("403"):
        await msg.finish(I18NContext("maimai.message.forbidden"))
    if str(e).startswith("429"):
        await msg.send_message(I18NContext("maimai.message.oauth.rate_limit"))
    Logger.exception()


async def _with_cache(msg: Bot.MessageSession, cache_file, fetch):
    """执行一次取数，成功则写缓存，失败则提示用户并退回本地缓存。

    :param msg: 消息会话。
    :param cache_file: 缓存文件路径。
    :param fetch: 无参协程函数，返回可 JSON 序列化的数据。
    :return: 取回的数据或缓存中的数据。
    """
    try:
        data = await fetch()
    except Exception as e:
        await _prompt_error(msg, e)
        if not cache_file.exists():
            raise e
        try:
            with open(cache_file, "rb") as f:
                data = orjson.loads(f.read())
        except Exception:
            raise e
        await msg.send_message(I18NContext("maimai.message.use_cache"))
        return data
    if data:
        try:
            with open(cache_file, "wb") as f:
                f.write(orjson.dumps(data))
        except Exception:
            Logger.exception()
    return data


def _require_oauth() -> None:
    """未登记 OAuth 应用时，用户态接口一概不可用。"""
    if not LXNS_OAUTH_ENABLED:
        raise ConfigValueError("{I18N:error.config.secret.not_found}")


async def fetch_player(bind_info: LxnsProberBindInfo) -> dict:
    """取回玩家信息。

    :param bind_info: 该用户的绑定记录。
    :return: 玩家信息，含 `name` 与 `rating`。
    """
    profile = unwrap(await request_player_data(bind_info, LXNS_MAIMAI_PLAYER_URL))
    return profile if isinstance(profile, dict) else {}


async def fetch_scores(bind_info: LxnsProberBindInfo) -> list[dict]:
    """取回该账号的全部成绩（落雪原始字段）。

    :param bind_info: 该用户的绑定记录。
    :return: 成绩列表。
    """
    resp = unwrap(await request_player_data(bind_info, LXNS_MAIMAI_SCORES_URL))
    scores = resp.get("scores", []) if isinstance(resp, dict) else resp
    if not isinstance(scores, list):
        return []
    return [score for score in scores if isinstance(score, dict)]


async def load_scores(msg: Bot.MessageSession, bind_info: LxnsProberBindInfo, use_cache: bool = True) -> list[dict]:
    """取回全量成绩，可按需读写本地缓存。

    :param msg: 消息会话。
    :param bind_info: 该用户的绑定记录。
    :param use_cache: 是否读写本地缓存。
    :return: 落雪原始字段的成绩列表。
    """
    if not use_cache:
        return await fetch_scores(bind_info)
    return await _with_cache(msg, _cache_file(msg, "maimaidx_lx_scores"), lambda: fetch_scores(bind_info))


async def map_scores(scores: list[dict]) -> list[dict]:
    """把落雪成绩逐条换算成水鱼形状，并补齐本地曲库中的定数。

    :param scores: 落雪原始字段的成绩列表。
    :return: 水鱼形状的成绩列表。
    """
    total = await total_list.get()
    return [map_score(score, total.by_id(lxns_to_df_id(score.get("id"), score.get("type")))) for score in scores]


async def get_total_record_lx(
    msg: Bot.MessageSession,
    utage: bool = False,
    use_cache: bool = True,
) -> dict:
    """取回完整成绩，形状与水鱼的 `/player/records` 一致。

    :param msg: 消息会话。
    :param utage: 是否保留宴会场曲目。
    :param use_cache: 是否读写本地缓存。
    :return: 含 `nickname`、`rating` 与 `records` 的成绩字典。
    """
    _require_oauth()
    bind_info = await get_bind_info(msg)

    async def fetch():
        player = await fetch_player(bind_info)
        records = await map_scores(await fetch_scores(bind_info))
        if not utage:
            records = [record for record in records if int(record["song_id"] or 0) < MAIMAI_UTAGE_ID_MIN]
        return {
            "nickname": player.get("name", ""),
            "username": player.get("name", ""),
            "rating": player.get("rating", 0),
            "records": records,
        }

    return await _with_cache(msg, _cache_file(msg, "maimaidx_lx_total_record"), fetch)


async def split_bests(scores: list[dict]) -> dict:
    """把落雪成绩按谱面类型划分为 B35 与 B15。

    :param scores: 落雪原始字段的成绩列表。
    :return: 含 `sd` 与 `dx` 两份成绩列表的字典。
    """
    records = await map_scores(scores)
    return {
        "sd": top_rated([record for record in records if record["type"] == "SD"], 35),
        "dx": top_rated([record for record in records if record["type"] == "DX"], 15),
    }


async def get_record_lx_oauth(msg: Bot.MessageSession, bind_info: LxnsProberBindInfo, use_cache: bool = True) -> dict:
    """以 OAuth 令牌取回 B35 与 B15，形状与水鱼的 `/query/player` 一致。

    落雪的用户态文档只列出玩家信息与全量成绩两个端点，`bests` 属未文档化的前端接口：取不到
    时退化为按谱面类型从全量成绩里各取前 35 / 15 张，与官方按旧曲、现曲划分的 B35 / B15
    可能略有出入。

    :param msg: 消息会话。
    :param bind_info: 该用户的落雪绑定记录。
    :param use_cache: 是否读写本地缓存。
    :return: 含 `nickname`、`rating` 与 `charts.sd` / `charts.dx` 的成绩字典。
    """
    _require_oauth()

    async def fetch():
        player = await fetch_player(bind_info)
        try:
            resp = unwrap(await request_player_data(bind_info, LXNS_MAIMAI_BESTS_URL))
        except LxnsTokenRevoked:
            raise
        except Exception:
            # 该端点未见于文档，落雪调整接口时不应连带毁掉 B50，故退回全量成绩自行划分。
            Logger.exception()
            resp = None
        if isinstance(resp, dict) and (resp.get("standard") or resp.get("dx")):
            charts = await split_bests(list(resp.get("standard") or []) + list(resp.get("dx") or []))
        else:
            charts = await split_bests(await fetch_scores(bind_info))
        return {
            "nickname": player.get("name", ""),
            "username": player.get("name", ""),
            "rating": player.get("rating", 0),
            "charts": charts,
        }

    return await _with_cache(msg, _cache_file(msg, "maimaidx_lx_bests"), fetch)


async def get_record_lx(
    msg: Bot.MessageSession,
    token: LxnsProberBindInfo | None = None,
    use_cache: bool = True,
) -> dict:
    """取回 B35 与 B15，形状与水鱼的 `/query/player` 一致。

    查询对象由令牌决定：落雪的用户态端点按令牌认出用户，没有别的识别方式。

    :param msg: 消息会话。
    :param token: 该用户的落雪绑定记录；为空时自行解析。
    :param use_cache: 是否读写本地缓存。
    :return: 含 `nickname`、`rating` 与 `charts.sd` / `charts.dx` 的成绩字典。
    """
    if not token or not token.refresh_token:
        token = await get_bind_info(msg)
    return await get_record_lx_oauth(msg, token, use_cache)


async def get_song_record_lx(msg: Bot.MessageSession, sid: str | list[str], use_cache: bool = True) -> dict:
    """取某首歌全部难度的成绩，形状与水鱼的 `/player/record` 一致。

    落雪没有等价的按曲查询端点（`/bests` 只给最佳成绩），故从全量成绩里筛出目标曲目。

    :param msg: 消息会话。
    :param sid: 水鱼风格的曲目 ID，可为列表。
    :param use_cache: 是否读写本地缓存。
    :return: 曲目 ID 到该曲成绩列表的映射；无成绩时为空字典。
    """
    ids = [str(s) for s in (sid if isinstance(sid, list) else [sid])]
    data = await get_total_record_lx(msg, utage=True, use_cache=use_cache)
    result = {}
    for i in ids:
        entries = [record for record in data.get("records", []) if str(record["song_id"]) == i]
        if entries:
            result[i] = entries
    return result


async def get_plate_lx(msg: Bot.MessageSession, payload: dict, version: str, use_cache: bool = True) -> dict:
    """按版本整理出名牌板所需的成绩列表，形状与水鱼的 `verlist` 一致。

    落雪没有水鱼那样的名牌板端点，只能取回全量成绩后按本地曲库的版本自行筛选；本地缺曲时
    无从判断版本，该条成绩便不计入。

    :param msg: 消息会话。
    :param payload: 承载版本列表的载荷，由调用方按名牌板填入。
    :param version: 名牌板的版本标识；载荷未给出版本名时据此推断。
    :param use_cache: 是否读写本地缓存。
    :return: 含 `verlist` 的成绩字典。
    """
    _require_oauth()
    bind_info = await get_bind_info(msg)
    versions = {str(v) for v in (payload or {}).get("version", [])} or set(plate_versions(version))

    async def fetch():
        total = await total_list.get()
        verlist = []
        for score in await load_scores(msg, bind_info, use_cache):
            song_id = lxns_to_df_id(score.get("id"), score.get("type"))
            if not song_id or int(song_id) >= MAIMAI_UTAGE_ID_MIN:
                continue
            music = total.by_id(song_id)
            if versions and (not music or music.get("basic_info", {}).get("from") not in versions):
                continue
            verlist.append(
                {
                    "id": song_id,
                    "level_index": int(score.get("level_index") or 0),
                    "achievements": float(score.get("achievements") or 0),
                    "fc": score.get("fc") or "",
                    "fs": score.get("fs") or "",
                }
            )
        return {"verlist": verlist}

    return await _with_cache(msg, _cache_file(msg, f"maimaidx_lx_plate_{version}"), fetch)
