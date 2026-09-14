"""落雪咖啡屋（LXNS）接入的纯逻辑单元测试：ID 换算、成绩换算、数据源选择与 OAuth 工具。"""

import inspect
from unittest.mock import patch

from core.constants.exceptions import ConfigValueError
from core.tester import func_case, Tester
from modules.maimai.database.models import LxnsProberBindInfo
from modules.maimai.libraries import lxns_apidata, lxns_oauth, maimaidx_apidata
from modules.maimai.libraries.lxns_apidata import (
    LXNS_MAIMAI_BESTS_BY_FRIEND_CODE_URL,
    LXNS_MAIMAI_PLAYER_BY_FRIEND_CODE_URL,
    df_to_lxns_id,
    get_record_lx,
    get_record_lx_dev,
    is_dx_id,
    lxns_to_df_id,
    map_bests,
    map_score,
    plate_versions,
    score_rating,
    top_rated,
)
from modules.maimai.libraries.maimaidx_utils import compute_rating
from modules.maimai.libraries.lxns_oauth import (
    _extract_bind_code,
    build_authorize_url,
    fetch_player_field,
    unwrap,
)
from modules.maimai.libraries.source import (
    GAME_CHUNITHM,
    GAME_MAIMAI,
    SOURCE_DIVING_FISH,
    SOURCE_LXNS,
    default_source,
    lxns_bind_usable,
    pick_source,
    toggle_source,
)


class _UnionInfo:
    """只带 `sender_data` 的联合信息替身。"""

    def __init__(self, sender_data: dict):
        self.sender_data = sender_data


class _SessionInfo:
    def __init__(self, sender_data: dict):
        self.sender_union_info = _UnionInfo(sender_data)
        self.prefixes = ["~"]


class _MessageSession:
    """只带会话信息的消息会话替身。"""

    def __init__(self, sender_data: dict):
        self.session_info = _SessionInfo(sender_data)

    async def finish(self, *args, **kwargs):
        raise AssertionError("Pure logic should not finish the session.")


async def _test_lxns_id_conversion():
    """舞萌 DX 谱面的 ID 换算应对称，宴会场曲目不参与换算"""
    return (
        lxns_to_df_id(834, "dx") == "10834"
        and lxns_to_df_id(834, "standard") == "834"
        and lxns_to_df_id(100001, "utage") == "100001"
        and lxns_to_df_id(None, "dx") == ""
        and lxns_to_df_id("abc", "dx") == ""
        and df_to_lxns_id("10834") == "834"
        and df_to_lxns_id(10834) == "834"
        and df_to_lxns_id("834") == "834"
        and df_to_lxns_id("100001") == "100001"
        and is_dx_id("10834")
        and not is_dx_id("834")
        and not is_dx_id("100001")
        and not is_dx_id("abc")
        and df_to_lxns_id(lxns_to_df_id(1234, "dx")) == "1234"
    )


async def _test_map_score_with_local_music():
    """有本地曲目时，成绩应取本地定数，字段名换算为水鱼形状"""
    score = {
        "id": 834,
        "type": "dx",
        "song_name": "FESTiVAL",
        "level": "14+",
        "level_index": 4,
        "achievements": 100.5,
        "fc": "app",
        "fs": None,
        "dx_score": 3012,
        "dx_rating": 320.4,
        "rate": "sssp",
    }
    music = {"ds": [4.0, 7.0, 11.0, 13.5, 14.7], "title": "FESTiVAL"}
    mapped = map_score(score, music)
    return (
        mapped["song_id"] == "10834"
        and mapped["title"] == "FESTiVAL"
        and mapped["type"] == "DX"
        and mapped["level"] == "14+"
        and mapped["level_index"] == 4
        and mapped["ds"] == 14.7
        and mapped["achievements"] == 100.5
        and mapped["fc"] == "app"
        and mapped["fs"] == ""
        and mapped["dxScore"] == 3012
        and mapped["rate"] == "sssp"
        and mapped["ra"] == 320
    )


async def _test_map_score_without_local_music():
    """本地缺曲时定数记 0，曲名留空，其余字段仍需可用"""
    mapped = map_score({"id": 3, "type": "standard", "level_index": 2}, None)
    return (
        mapped["song_id"] == "3"
        and mapped["title"] == ""
        and mapped["type"] == "SD"
        and mapped["ds"] == 0.0
        and mapped["level_index"] == 2
        and mapped["achievements"] == 0.0
        and mapped["fc"] == ""
        and mapped["dxScore"] == 0
        and mapped["rate"] == ""
        and mapped["ra"] == 0
    )


async def _test_score_rating_fallback():
    """接口未给单曲 Rating 时应按定数与达成率推算，本地缺曲则记 0"""
    score = {"achievements": 100.5}
    return (
        score_rating({"dx_rating": 320.4}, 14.7) == 320
        and score_rating(score, 14.7) == compute_rating(14.7, 100.5)
        and score_rating(score, 0.0) == 0
    )


class _EmptyTotalList:
    """测试用曲库替身：一律视为本地缺曲，免得测试去联网取曲目表。"""

    async def get(self):
        return self

    def by_id(self, song_id):
        return None


async def _test_top_rated_orders_and_limits():
    """Best 列表应按单曲 Rating 降序取前若干条"""
    records = [{"ra": 100}, {"ra": 300}, {"ra": 200}]
    return [record["ra"] for record in top_rated(records, 2)] == [300, 200] and top_rated([], 5) == []


async def _test_map_bests_keeps_official_pools():
    """接口的 standard 与 dx 就是 B35 与 B15：旧曲里的 DX 谱面留在 B35，不得并入 B15"""
    bests = {
        "standard": [
            {
                "id": 834,
                "type": "dx",
                "level_index": 3,
                "achievements": 100.5,
                "dx_rating": 320,
                "song_name": "旧曲 DX",
            },
            {
                "id": 100,
                "type": "standard",
                "level_index": 3,
                "achievements": 99.5,
                "dx_rating": 300,
                "song_name": "旧曲 SD",
            },
        ],
        "dx": [
            {
                "id": 1234,
                "type": "dx",
                "level_index": 3,
                "achievements": 100.0,
                "dx_rating": 310,
                "song_name": "现曲 DX",
            }
        ],
    }
    with patch.object(lxns_apidata, "total_list", _EmptyTotalList()):
        charts = await map_bests(bests)
        empty = await map_bests(None)

    return (
        [(chart["song_id"], chart["type"]) for chart in charts["sd"]] == [("10834", "DX"), ("100", "SD")]
        and [(chart["song_id"], chart["type"]) for chart in charts["dx"]] == [("11234", "DX")]
        and empty == {"sd": [], "dx": []}
    )


async def _test_source_selection():
    """默认数据源为舞萌水鱼、中二落雪（落雪不可用时退回水鱼），并兼容中二的旧键名与非法值"""
    empty = _MessageSession({})
    return (
        default_source(GAME_MAIMAI) == SOURCE_DIVING_FISH
        and pick_source(empty, GAME_MAIMAI) == SOURCE_DIVING_FISH
        and pick_source(empty, GAME_CHUNITHM) == default_source(GAME_CHUNITHM)
        and pick_source(_MessageSession({"maimaidx_record_source": "lxns"}), GAME_MAIMAI) == SOURCE_LXNS
        and pick_source(_MessageSession({"chunithum_record_source": "lxns"}), GAME_CHUNITHM) == SOURCE_LXNS
        and pick_source(_MessageSession({"chunithum_record_source": "diving-fish"}), GAME_CHUNITHM)
        == SOURCE_DIVING_FISH
        and pick_source(_MessageSession({"maimaidx_record_source": "unknown"}), GAME_MAIMAI) == SOURCE_DIVING_FISH
        and toggle_source(SOURCE_LXNS) == SOURCE_DIVING_FISH
        and toggle_source(SOURCE_DIVING_FISH) == SOURCE_LXNS
    )


async def _test_lxns_bind_usable():
    """落雪绑定可用性：授权过且落雪已配置才可用，仅有好友码的旧记录一律不可用"""
    return (
        lxns_bind_usable("token", True)
        and not lxns_bind_usable(None, True)
        and not lxns_bind_usable("", True)
        and not lxns_bind_usable("token", False)
    )


async def _test_lxns_bind_info_keeps_no_subject():
    """落雪靠 refresh token 自行轮换，绑定表与写入方法都不该保存令牌里的 `sub`

    水鱼要用用户 ID 去换票，落雪则不需要：`sub` 只在绑定时用于向用户确认账号。
    """
    return (
        "subject" not in LxnsProberBindInfo._meta.fields_map
        and "subject" not in inspect.signature(LxnsProberBindInfo.set_bind_info).parameters
        and "subject" not in inspect.signature(LxnsProberBindInfo.update_refresh_token).parameters
    )


async def _test_lxns_record_route():
    """落雪取分一律走用户态接口；带不出令牌的旧记录与未绑定用户都转去取当前绑定"""
    oauth_bind = LxnsProberBindInfo(union_id="u", refresh_token="token")
    legacy_bind = LxnsProberBindInfo(union_id="u", refresh_token=None)
    calls = []

    async def fake_oauth(msg, bind_info, use_cache=True):
        calls.append((bind_info, use_cache))
        return {"charts": {}}

    async def fake_bind_info(msg):
        calls.append("rebind")
        return oauth_bind

    with (
        patch.object(lxns_apidata, "get_record_lx_oauth", fake_oauth),
        patch.object(lxns_apidata, "get_bind_info", fake_bind_info),
        patch.object(lxns_apidata, "LXNS_DEVELOPER_ENABLED", False),
    ):
        data = await get_record_lx(_MessageSession({}), oauth_bind, use_cache=False)
        alias = await get_record_lx(_MessageSession({}), None, use_cache=False)
        legacy = await get_record_lx(_MessageSession({}), legacy_bind, use_cache=False)

    return (
        data == {"charts": {}}
        and alias == {"charts": {}}
        and legacy == {"charts": {}}
        and calls == [(oauth_bind, False), "rebind", (oauth_bind, False), "rebind", (oauth_bind, False)]
    )


async def _test_lxns_friend_code_route():
    """落雪取分按查询对象分流：给出好友码走开发者端点，未配置密钥时退回用户态端点"""
    bind = LxnsProberBindInfo(union_id="u", refresh_token="token")
    calls = []

    async def fake_dev(msg, friend_code, use_cache=True):
        calls.append(("dev", friend_code, use_cache))
        return {"charts": {}}

    async def fake_oauth(msg, bind_info, use_cache=True):
        calls.append(("oauth", bind_info.union_id, use_cache))
        return {"charts": {}}

    async def fake_field(bind_info, field, url=None):
        calls.append(("field", field))
        return "888888888888888"

    empty = _MessageSession({})
    with (
        patch.object(lxns_apidata, "get_record_lx_dev", fake_dev),
        patch.object(lxns_apidata, "get_record_lx_oauth", fake_oauth),
    ):
        # 未配置开发者密钥时：给出好友码照样走开发者端点，查自己则回到用户态端点。
        with patch.object(lxns_apidata, "LXNS_DEVELOPER_ENABLED", False):
            explicit = await get_record_lx(empty, None, "1234567890", use_cache=False)
            fallback = await get_record_lx(empty, bind, use_cache=False)
        # 配置了密钥则先用资料里的好友码，改走开发者端点。测试自带密钥开关，不受配置文件影响。
        with (
            patch.object(lxns_apidata, "LXNS_DEVELOPER_ENABLED", True),
            patch.object(lxns_apidata, "fetch_player_field", fake_field),
        ):
            resolved = await get_record_lx(empty, bind, use_cache=False)

    return (
        explicit == {"charts": {}}
        and fallback == {"charts": {}}
        and resolved == {"charts": {}}
        and calls
        == [
            ("dev", "1234567890", False),
            ("oauth", "u", False),
            ("field", "friend_code"),
            ("dev", "888888888888888", False),
        ]
    )


async def _test_lxns_developer_required():
    """未配置开发者密钥时按好友码查询应直接报错，而不是发出注定被拒的请求"""
    with patch.object(lxns_apidata, "LXNS_DEVELOPER_ENABLED", False):
        try:
            await get_record_lx_dev(_MessageSession({}), "1234567890", use_cache=False)
        except ConfigValueError:
            return True
    return False


async def _test_lxns_developer_urls():
    """落雪的 Best 应落在按好友码寻址的开发者端点上"""
    return (
        LXNS_MAIMAI_PLAYER_BY_FRIEND_CODE_URL.format(friend_code=1234567890)
        == "https://maimai.lxns.net/api/v0/maimai/player/1234567890"
        and LXNS_MAIMAI_BESTS_BY_FRIEND_CODE_URL.format(friend_code=1234567890)
        == "https://maimai.lxns.net/api/v0/maimai/player/1234567890/bests"
    )


async def _test_fetch_player_field():
    """好友码取自授权账号的个人资料，取不到时留空以便退回用户态端点"""
    bind = LxnsProberBindInfo(union_id="u", refresh_token="token")

    async def fake_data(bind_info, url, **kwargs):
        return {"success": True, "code": 200, "data": {"name": "Lxns", "friend_code": 888888888888888}}

    async def failing_data(bind_info, url, **kwargs):
        raise Exception("500 Internal Server Error")

    with patch.object(lxns_oauth, "request_player_data", fake_data):
        name = await fetch_player_field(bind, "name")
        code = await fetch_player_field(bind, "friend_code")
        missing = await fetch_player_field(bind, "absent")
    with patch.object(lxns_oauth, "request_player_data", failing_data):
        failed = await fetch_player_field(bind, "friend_code")

    return name == "Lxns" and code == "888888888888888" and missing == "" and failed == ""


async def _test_get_record_forwards_use_cache():
    """水鱼侧取分转发落雪时，好友码与 use_cache 都必须走关键字传参，否则会被顶到查询对象的位置上"""
    received = []
    empty = _MessageSession({})

    async def fake_record_lx(msg, token=None, friend_code="", use_cache=True):
        received.append((friend_code, use_cache))
        return {"charts": {}}

    with (
        patch.object(maimaidx_apidata, "get_record_lx", fake_record_lx),
        patch.object(maimaidx_apidata, "pick_source", lambda msg, game: SOURCE_LXNS),
    ):
        own = await maimaidx_apidata.get_record(empty, {}, use_cache=False)
        other = await maimaidx_apidata.get_record(empty, None, "1234567890", use_cache=False)

    return own == {"charts": {}} and other == {"charts": {}} and received == [("", False), ("1234567890", False)]


async def _test_authorize_url_params():
    """授权链接应带上授权码流程与回调地址，且不带 PKCE 与 state"""
    url = build_authorize_url()
    return (
        url.startswith("https://maimai.lxns.net/oauth/authorize?")
        and "response_type=code" in url
        and "scope=read_player" in url
        and "redirect_uri=" in url
        and "code_challenge" not in url
        and "code_verifier" not in url
        and "state=" not in url
    )


async def _test_extract_bind_code():
    """用户发来的授权码应能从引号、空白与整串回调地址里取出"""
    return (
        _extract_bind_code("abc123") == "abc123"
        and _extract_bind_code("  abc123\n") == "abc123"
        and _extract_bind_code("“abc123”") == "abc123"
        and _extract_bind_code("https://example.com/callback?code=abc123&state=x") == "abc123"
        and _extract_bind_code("https://example.com/callback?code=a%2Fb") == "a/b"
        and _extract_bind_code("https://example.com/callback") == ""
        and _extract_bind_code("") == ""
    )


async def _test_unwrap_data_field():
    """落雪接口的 data 包裹应被取出，未被包裹的响应保持原样"""
    return (
        unwrap({"success": True, "code": 200, "data": {"name": "Lxns"}}) == {"name": "Lxns"}
        and unwrap({"name": "Lxns"}) == {"name": "Lxns"}
        and unwrap([1, 2]) == [1, 2]
    )


async def _test_plate_versions():
    """名牌板的版本标识应能映射到查分器版本名，未知标识不留版本筛选"""
    return (
        plate_versions("真") == ["maimai", "maimai PLUS"]
        and plate_versions("初") == []
        and plate_versions("不存在") == []
        and "maimai" in plate_versions("覇")
        and plate_versions("熊") == ["maimai でらっくす"]
    )


@func_case
async def test_maimai_lxns(tester: Tester):
    await tester.test(_test_lxns_id_conversion, "落雪与水鱼曲目 ID 对称换算")
    await tester.test(_test_map_score_with_local_music, "成绩换算（有本地曲目）")
    await tester.test(_test_map_score_without_local_music, "成绩换算（本地缺曲）")
    await tester.test(_test_score_rating_fallback, "单曲 Rating 缺失时推算")
    await tester.test(_test_top_rated_orders_and_limits, "Best 列表排序与截断")
    await tester.test(_test_map_bests_keeps_official_pools, "落雪 Best 的新旧曲划分")
    await tester.test(_test_source_selection, "数据源选择与切换")
    await tester.test(_test_lxns_bind_usable, "落雪绑定可用性判断")
    await tester.test(_test_lxns_bind_info_keeps_no_subject, "落雪绑定表不保存用户 ID")
    await tester.test(_test_lxns_record_route, "落雪取分路由选择（无开发者密钥）")
    await tester.test(_test_lxns_friend_code_route, "落雪按好友码取分的路由")
    await tester.test(_test_lxns_developer_required, "未配置开发者密钥时的按好友码查询")
    await tester.test(_test_lxns_developer_urls, "落雪开发者端点地址")
    await tester.test(_test_fetch_player_field, "落雪个人资料字段读取")
    await tester.test(_test_get_record_forwards_use_cache, "水鱼侧取分转发落雪参数")
    await tester.test(_test_authorize_url_params, "授权链接参数")
    await tester.test(_test_extract_bind_code, "授权码提取")
    await tester.test(_test_unwrap_data_field, "接口 data 包裹解析")
    await tester.test(_test_plate_versions, "名牌板版本标识映射")
    return tester
