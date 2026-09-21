"""CHUNITHM 接入的纯逻辑单元测试：水鱼公开端点的成绩换算、取分路由与开发者端点地址。"""

from unittest.mock import patch

import orjson

from core.constants.exceptions import ConfigValueError
from core.tester import Tester, func_case
from modules.maimai.database.models import DivingProberBindInfo, LxnsProberBindInfo
from modules.maimai.libraries import chunithm_apidata
from modules.maimai.libraries.chunithm_apidata import (
    get_record_df,
    get_record_df_by_username,
    get_record_lx,
    get_record_lx_dev,
    map_df_chunithm_record,
)

DF_QUERY_URL = "https://www.diving-fish.com/api/chunithmprober/query/player"


class _SessionInfo:
    def __init__(self, sender_id: str = "u|1"):
        self.sender_id = sender_id
        self.prefixes = ["~"]


class _MessageSession:
    def __init__(self, sender_id: str = "u|1"):
        self.session_info = _SessionInfo(sender_id)

    async def finish(self, *args, **kwargs):
        raise AssertionError("This case should not finish the session.")

    async def send_message(self, *args, **kwargs):
        raise AssertionError("This case should not send messages.")


def _df_record(**overrides) -> dict:
    record = {
        "mid": 1,
        "title": "Song",
        "level_label": "Master",
        "ds": 15.0,
        "score": 1010000,
        "ra": 15.5,
        "fc": "",
    }
    record.update(overrides)
    return record


async def _test_map_df_chunithm_record():
    master = map_df_chunithm_record(_df_record(fc="alljustice"))
    ultima = map_df_chunithm_record({"id": 456, "level_label": "Ultima"})
    explicit = map_df_chunithm_record({"mid": 789, "level_label": "Expert", "level_index": 1})
    unknown = map_df_chunithm_record({})
    return (
        master["mid"] == 1
        and master["level_index"] == 3
        and master["level"] == "Master"
        and master["ds"] == 15.0
        and master["score"] == 1010000
        and master["ra"] == 15.5
        and master["fc"] == "alljustice"
        and ultima["mid"] == 456
        and ultima["level_index"] == 4
        and ultima["level"] == "Ultima"
        and explicit["level_index"] == 1
        and unknown["mid"] == ""
        and unknown["level"] == ""
        and unknown["level_index"] == 0
    )


async def _test_df_username_mapping():
    captured = {}

    async def fake_post(url, data=None, **kwargs):
        captured["url"] = url
        captured["payload"] = orjson.loads(data)
        return {
            "username": "someone",
            "rating": 16.12,
            "records": {
                "b30": [_df_record(mid=1)],
                "n20": [_df_record(mid=2, level_label="Ultima")],
            },
        }

    with patch.object(chunithm_apidata, "post_url", fake_post):
        data = await get_record_df_by_username("someone")

    return (
        captured["url"] == DF_QUERY_URL
        and captured["payload"] == {"username": "someone"}
        and data["nickname"] == "someone"
        and data["rating"] == 16.12
        and [record["mid"] for record in data["records"]["b30"]] == [1]
        and [record["level_index"] for record in data["records"]["n20"]] == [4]
    )


async def _test_df_username_legacy_records():

    async def fake_post(url, data=None, **kwargs):
        return {
            "username": "someone",
            "rating": 16.12,
            "records": {"b30": [_df_record(mid=1)], "r10": [_df_record(mid=2)]},
        }

    with patch.object(chunithm_apidata, "post_url", fake_post):
        data = await get_record_df_by_username("someone")

    return [record["mid"] for record in data["records"]["b30"]] == [1] and [
        record["mid"] for record in data["records"]["n20"]
    ] == [2]


async def _test_df_record_route():
    calls = []
    bind = DivingProberBindInfo(union_id="u", refresh_token="token", subject=None)

    async def fake_username(username):
        calls.append(("username", username))
        return {"records": {"b30": [], "n20": []}}

    async def fake_token(bind_info):
        calls.append(("token", bind_info.union_id))
        return {"records": {"b30": [], "n20": []}}

    with (
        patch.object(chunithm_apidata, "DF_OAUTH_ENABLED", True),
        patch.object(chunithm_apidata, "get_record_df_by_username", fake_username),
        patch.object(chunithm_apidata, "get_record_df_by_token", fake_token),
    ):
        other = await get_record_df(_MessageSession(), None, "someone", use_cache=True)
        own = await get_record_df(_MessageSession(), bind, use_cache=False)

    return (
        other == {"records": {"b30": [], "n20": []}}
        and own == {"records": {"b30": [], "n20": []}}
        and calls == [("username", "someone"), ("token", "u")]
    )


async def _test_lxns_record_route():
    calls = []
    bind = LxnsProberBindInfo(union_id="u", refresh_token="token")

    async def fake_dev(msg, friend_code, use_cache=True):
        calls.append(("dev", friend_code, use_cache))
        return {"records": {}}

    async def fake_oauth(msg, bind_info, use_cache=True):
        calls.append(("oauth", bind_info.union_id, use_cache))
        return {"records": {}}

    async def fake_field(bind_info, field, url=None):
        calls.append(("field", field))
        return "888888888888888"

    empty = _MessageSession()
    with (
        patch.object(chunithm_apidata, "get_record_lx_dev", fake_dev),
        patch.object(chunithm_apidata, "get_record_lx_oauth", fake_oauth),
    ):
        # 未配置开发者密钥时：给出好友码照样走开发者端点，查自己则回到用户态端点。
        with patch.object(chunithm_apidata, "LXNS_DEVELOPER_ENABLED", False):
            explicit = await get_record_lx(empty, None, "1234567890", use_cache=False)
            fallback = await get_record_lx(empty, bind, use_cache=False)
        # 配置了密钥则先用资料里的好友码，改走开发者端点。测试自带密钥开关，不受配置文件影响。
        with (
            patch.object(chunithm_apidata, "LXNS_DEVELOPER_ENABLED", True),
            patch.object(chunithm_apidata, "fetch_player_field", fake_field),
        ):
            resolved = await get_record_lx(empty, bind, use_cache=False)

    return (
        explicit == {"records": {}}
        and fallback == {"records": {}}
        and resolved == {"records": {}}
        and calls
        == [
            ("dev", "1234567890", False),
            ("oauth", "u", False),
            ("field", "friend_code"),
            ("dev", "888888888888888", False),
        ]
    )


async def _test_lxns_developer_required():
    with patch.object(chunithm_apidata, "LXNS_DEVELOPER_ENABLED", False):
        try:
            await get_record_lx_dev(_MessageSession(), "1234567890", use_cache=False)
        except ConfigValueError:
            return True
    return False


async def _test_lxns_developer_urls():
    return (
        chunithm_apidata.LXNS_CHUNITHM_PLAYER_BY_FRIEND_CODE_URL.format(friend_code=1234567890)
        == "https://maimai.lxns.net/api/v0/chunithm/player/1234567890"
        and chunithm_apidata.LXNS_CHUNITHM_BESTS_BY_FRIEND_CODE_URL.format(friend_code=1234567890)
        == "https://maimai.lxns.net/api/v0/chunithm/player/1234567890/bests"
    )


@func_case
async def test_maimai_chunithm(tester: Tester):
    await tester.test(_test_map_df_chunithm_record, "水鱼公开端点成绩换算")
    await tester.test(_test_df_username_mapping, "按用户名查询的两段成绩")
    await tester.test(_test_df_username_legacy_records, "旧版按用户名查询的成绩段")
    await tester.test(_test_df_record_route, "水鱼取分路由选择")
    await tester.test(_test_lxns_record_route, "落雪取分路由选择")
    await tester.test(_test_lxns_developer_required, "未配置开发者密钥时的按好友码查询")
    await tester.test(_test_lxns_developer_urls, "落雪开发者端点地址")
    return tester
