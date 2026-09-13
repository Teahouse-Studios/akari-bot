"""落雪咖啡屋（LXNS）接入的纯逻辑单元测试：ID 换算、成绩换算、数据源选择与 OAuth 工具。"""

from unittest.mock import patch

from core.constants.exceptions import ConfigValueError
from core.tester import func_case, Tester
from modules.maimai.database.models import LxnsProberBindInfo
from modules.maimai.libraries import lxns_apidata, maimaidx_apidata
from modules.maimai.libraries.lxns_apidata import (
    df_to_lxns_id,
    get_record_lx,
    is_dx_id,
    lxns_to_df_id,
    map_score,
    plate_versions,
    score_rating,
    top_rated,
)
from modules.maimai.libraries.maimaidx_utils import compute_rating
from modules.maimai.libraries.lxns_oauth import (
    build_authorize_url,
    generate_code_challenge,
    generate_code_verifier,
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


async def _test_top_rated_orders_and_limits():
    """Best 列表应按单曲 Rating 降序取前若干条"""
    records = [{"ra": 100}, {"ra": 300}, {"ra": 200}]
    return [record["ra"] for record in top_rated(records, 2)] == [300, 200] and top_rated([], 5) == []


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
    """落雪绑定可用性：授权过的必然可用，仅有好友码的要落雪已配置才可用"""
    return (
        lxns_bind_usable("token", "")
        and lxns_bind_usable("token", "123456")
        and lxns_bind_usable(None, "123456", True)
        and not lxns_bind_usable(None, "123456", False)
        and not lxns_bind_usable(None, "")
        and not lxns_bind_usable("", "")
    )


async def _test_lxns_record_route():
    """落雪取分路由：有令牌走用户态接口，仅有好友码走公开端点，两者皆无则判为未绑定"""
    oauth_bind = LxnsProberBindInfo(union_id="u", friend_code="", refresh_token="token")
    friend_bind = LxnsProberBindInfo(union_id="u", friend_code="123456789", refresh_token=None)
    calls = []
    empty = _MessageSession({})

    async def fake_oauth(msg, bind_info, use_cache=True):
        calls.append(("oauth", bind_info, use_cache))
        return {"charts": {}}

    async def fake_friend(msg, friend_code, use_cache=True):
        calls.append(("friend", friend_code, use_cache))
        return {"charts": {}}

    async def fake_prober(msg):
        calls.append(("prober", None, None))
        return friend_bind

    with (
        patch.object(lxns_apidata, "get_record_lx_oauth", fake_oauth),
        patch.object(lxns_apidata, "get_record_lx_friend", fake_friend),
        patch.object(lxns_apidata, "get_lxns_prober_bind_info", fake_prober),
        patch.object(lxns_apidata, "LX_DEVELOPER_TOKEN", "developer-token"),
    ):
        await get_record_lx(empty, oauth_bind, use_cache=False)
        await get_record_lx(empty, friend_bind, use_cache=False)
        await get_record_lx(empty, "987654321", use_cache=False)
        await get_record_lx(empty, None, use_cache=False)
        try:
            await get_record_lx(empty, "", use_cache=False)
        except ConfigValueError:
            rejected = True
        else:
            rejected = False

    return (
        [call[0] for call in calls] == ["oauth", "friend", "friend", "prober", "friend"]
        and calls[0][1] is oauth_bind
        and calls[1][1] == "123456789"
        and calls[2][1] == "987654321"
        and calls[4][1] == "123456789"
        and all(call[2] is False for call in calls if call[2] is not None)
        and rejected
    )


async def _test_get_record_forwards_use_cache():
    """水鱼侧 get_record 转发落雪时 use_cache 必须走关键字传参，否则会被顶到查询对象的位置上"""
    received = []
    empty = _MessageSession({})

    async def fake_record_lx(msg, token=None, use_cache=True):
        received.append((token, use_cache))
        return {"charts": {}}

    with (
        patch.object(maimaidx_apidata, "get_record_lx", fake_record_lx),
        patch.object(maimaidx_apidata, "pick_source", lambda msg, game: SOURCE_LXNS),
    ):
        data = await maimaidx_apidata.get_record(empty, {}, use_cache=False)

    return data == {"charts": {}} and received == [(None, False)]


async def _test_pkce_code_challenge():
    """PKCE 挑战值应按 S256 计算，且与 RFC 7636 的样例一致"""
    return (
        generate_code_challenge("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk")
        == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    )


async def _test_code_verifier_is_random_and_urlsafe():
    """校验串应随机生成且仅含 URL 安全字符"""
    first = generate_code_verifier()
    second = generate_code_verifier()
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
    return len(first) >= 43 and first != second and set(first) <= allowed


async def _test_authorize_url_carries_pkce():
    """授权链接应带上授权码流程与 PKCE 所需参数"""
    url = build_authorize_url("challenge-value", "state-value")
    return (
        url.startswith("https://maimai.lxns.net/oauth/authorize?")
        and "response_type=code" in url
        and "scope=read_player" in url
        and "code_challenge=challenge-value" in url
        and "code_challenge_method=S256" in url
        and "state=state-value" in url
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
    await tester.test(_test_source_selection, "数据源选择与切换")
    await tester.test(_test_lxns_bind_usable, "落雪绑定可用性判断")
    await tester.test(_test_lxns_record_route, "落雪取分路由选择")
    await tester.test(_test_get_record_forwards_use_cache, "水鱼侧取分转发落雪参数")
    await tester.test(_test_pkce_code_challenge, "PKCE S256 挑战值")
    await tester.test(_test_code_verifier_is_random_and_urlsafe, "PKCE 校验串生成")
    await tester.test(_test_authorize_url_carries_pkce, "授权链接参数")
    await tester.test(_test_unwrap_data_field, "接口 data 包裹解析")
    await tester.test(_test_plate_versions, "名牌板版本标识映射")
    return tester
