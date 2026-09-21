"""phigros 旧版曲目信息兼容性单元测试。"""

from unittest.mock import patch

from core.builtins.session.features import Features
from core.builtins.session.info import SessionInfo
from core.builtins.session.internal import MessageSession
from core.constants.exceptions import SessionFinished
from core.tester import func_case, Tester
from modules.phigros import _require_song_info
from modules.phigros.libraries.assets import (
    is_legacy_song_info,
    parse_difficulty_tsv,
    to_difficulty_table,
)

# 旧版 update.py 的产出：曲目 id 归一化为小写、字段名为 composer、定数为字符串。
LEGACY_SONG_INFO = {
    "glaciaxion.sunsetray": {
        "name": "Glaciaxion",
        "composer": "SunsetRay",
        "diff": {"EZ": "1.0", "HD": "6.5", "IN": "12.6", "AT": "-"},
    },
    "credits.frums": {
        "name": "Credits",
        "composer": "Frums",
        "diff": {"EZ": "-", "HD": "-", "IN": "-"},
    },
}

# 现行 assets.py 的产出：曲目 id 保留原始大小写与标点、定数为浮点数。
CURRENT_SONG_INFO = {
    "Glaciaxion.SunsetRay": {
        "name": "Glaciaxion",
        "artist": "SunsetRay",
        "illustrator": "艾若拉",
        "charter": {"EZ": "Barbarianerman"},
        "diff": {"EZ": 1.0, "HD": 6.5, "IN": 12.6},
    },
}


def _test_to_difficulty_table_tolerates_legacy_values():
    table = to_difficulty_table(LEGACY_SONG_INFO)
    return table["glaciaxion.sunsetray"] == [1.0, 6.5, 12.6, 0.0, 0.0] and table["credits.frums"] == [0.0] * 5


def _test_to_difficulty_table_keeps_current_values():
    return to_difficulty_table(CURRENT_SONG_INFO)["Glaciaxion.SunsetRay"] == [1.0, 6.5, 12.6, 0.0, 0.0]


def _test_to_difficulty_table_pads_five_slots():
    table = to_difficulty_table({"a.b": {"diff": {"EZ": 1.0}}, "c.d": {}})
    return len(table["a.b"]) == 5 and table["c.d"] == [0.0] * 5


def _test_is_legacy_song_info():
    return (
        is_legacy_song_info(LEGACY_SONG_INFO) is True
        and is_legacy_song_info(CURRENT_SONG_INFO) is False
        and is_legacy_song_info({}) is False
    )


def _test_is_legacy_song_info_detects_string_constant():
    return is_legacy_song_info({"a.b": {"name": "A", "artist": "B", "diff": {"EZ": "1.0"}}}) is True


def _test_parse_difficulty_tsv_skips_non_numeric():
    diff = parse_difficulty_tsv("Glaciaxion.SunsetRay\t1.0\t6.5\t-\n")
    return diff["Glaciaxion.SunsetRay"] == {"EZ": 1.0, "HD": 6.5}


async def _prompt_key_of(song_info: dict) -> str | None:
    session_info = await SessionInfo.assign(
        target_id="TEST|Group|phigros_legacy",
        target_from="TEST|Group",
        client_name="TEST",
        sender_id="TEST|1",
        features=Features(),
    )
    msg = MessageSession(session_info=session_info)
    captured = {}

    async def _finish(self, message_chain=None, **kwargs):
        captured["key"] = getattr(message_chain, "key", None)
        raise SessionFinished

    with (
        patch("modules.phigros.song_info_exists", return_value=True),
        patch("modules.phigros.load_song_info", return_value=song_info),
        patch.object(MessageSession, "finish", new=_finish),
    ):
        try:
            await _require_song_info(msg)
        except SessionFinished:
            return captured.get("key")
    return None


async def _test_require_song_info_rejects_legacy():
    return await _prompt_key_of(LEGACY_SONG_INFO) == "phigros.message.file_outdated"


async def _test_require_song_info_accepts_current():
    return await _prompt_key_of(CURRENT_SONG_INFO) is None


@func_case
async def test_phigros_legacy_assets(tester: Tester):
    """phigros: 旧版曲目信息的容错与识别"""
    await tester.test(_test_to_difficulty_table_tolerates_legacy_values, "旧版字符串定数容错")
    await tester.test(_test_to_difficulty_table_keeps_current_values, "现行定数取值不变")
    await tester.test(_test_to_difficulty_table_pads_five_slots, "定数表补齐五位")
    await tester.test(_test_is_legacy_song_info, "旧版结构识别")
    await tester.test(_test_is_legacy_song_info_detects_string_constant, "字符串定数识别")
    await tester.test(_test_parse_difficulty_tsv_skips_non_numeric, "TSV 占位符跳过")
    await tester.test(_test_require_song_info_rejects_legacy, "旧版结构拦截并引导重建")
    await tester.test(_test_require_song_info_accepts_current, "现行结构照常放行")
    return tester
