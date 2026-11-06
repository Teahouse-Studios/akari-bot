"""时区偏移取值来源测试。"""

from datetime import timedelta

from core.builtins.converter import converter
from core.builtins.session.info import SessionInfo
from core.config.base import CoreConfig
from core.database.models import TargetUnionInfo
from core.logger import Logger
from core.tester import func_case, Tester, mock_config

# 场景与用户数据中承载时区偏移的键，写入方为 modules/core/common_tools/setup.py
OFFSET_KEY = "timezone_offset"


async def _make_session(
    target_id: str,
    sender_id: str,
    target_offset: str | None = None,
    display_offset: str | None = None,
) -> SessionInfo:
    session_info = await SessionInfo.assign(
        target_id=target_id,
        target_from="TEST|Group",
        client_name="TEST",
        sender_id=sender_id,
    )
    if target_offset is not None:
        await session_info.target_union_info.edit_target_data(OFFSET_KEY, target_offset)
    if display_offset is not None:
        await session_info.sender_union_info.edit_sender_data(OFFSET_KEY, display_offset)
    return await SessionInfo.assign(
        target_id=target_id,
        target_from="TEST|Group",
        client_name="TEST",
        sender_id=sender_id,
    )


async def _test_offset_follows_target_data() -> bool:
    session_info = await _make_session("TEST|Group|tz_scene", "TEST|tz_scene", "+5:30")
    if session_info.timezone_offset != timedelta(hours=5, minutes=30):
        Logger.error(f"Session should adopt the configured offset, got {session_info.timezone_offset}")
        return False
    if session_info.tz_label != "+5:30":
        Logger.error(f"Session should keep the canonical offset label, got {session_info.tz_label!r}")
        return False
    return True


async def _test_core_default_used_when_target_unset() -> bool:
    with mock_config(CoreConfig, timezone_offset="+5:30"):
        session_info = await _make_session("TEST|Group|tz_core", "TEST|tz_core")
    if session_info.timezone_offset != timedelta(hours=5, minutes=30):
        Logger.error(f"Session should fall back to the core offset, got {session_info.timezone_offset}")
        return False
    if session_info.display_offset != timedelta(hours=5, minutes=30):
        Logger.error(f"Display offset should follow the scene offset, got {session_info.display_offset}")
        return False
    return True


async def _test_user_offset_only_affects_display() -> bool:
    session_info = await _make_session(
        "TEST|Group|tz_display",
        "TEST|tz_display",
        target_offset="+8",
        display_offset="-3",
    )
    if session_info.timezone_offset != timedelta(hours=8):
        Logger.error(f"User offset must not change the scene offset, got {session_info.timezone_offset}")
        return False
    if session_info.display_offset != timedelta(hours=-3):
        Logger.error(f"Display should use the user offset, got {session_info.display_offset}")
        return False
    if session_info.tz_label != "+8" or session_info.display_tz_label != "-3":
        Logger.error(
            f"Scene and display labels should be independent, got {session_info.tz_label!r} "
            f"and {session_info.display_tz_label!r}"
        )
        return False
    if session_info.now().utcoffset() != timedelta(hours=8):
        Logger.error("Business time must keep using the scene offset")
        return False
    return True


async def _test_invalid_target_offset_falls_back_to_core() -> bool:
    with mock_config(CoreConfig, timezone_offset="+5:30"):
        session_info = await _make_session("TEST|Group|tz_invalid", "TEST|tz_invalid", target_offset="+99:00")
    if session_info.timezone_offset != timedelta(hours=5, minutes=30):
        Logger.error(f"Invalid scene offset should fall back to the core offset, got {session_info.timezone_offset}")
        return False
    return True


async def _test_zero_offset_label() -> bool:
    session_info = await _make_session("TEST|Group|tz_zero", "TEST|tz_zero", target_offset="+0")
    if session_info.tz_label != "+0" or session_info.display_tz_label != "+0":
        Logger.error(f"Zero offset labels should be canonical, got {session_info.tz_label!r}")
        return False
    return True


def _test_session_info_serialization_preserves_offsets() -> bool:
    session_info = SessionInfo(
        target_id="TEST|Group|tz_serialize",
        target_from="TEST|Group",
        client_name="TEST",
        target_union_info=TargetUnionInfo(union_id="UTID|tz_serialize", target_data={}),
        tz_offset="+8",
        timezone_offset=timedelta(hours=8),
        display_tz_offset="-3",
        display_timezone_offset=timedelta(hours=-3),
    )
    restored = converter.structure(converter.unstructure(session_info), SessionInfo)
    if restored.timezone_offset != timedelta(hours=8) or restored.display_timezone_offset != timedelta(hours=-3):
        Logger.error("Session serialization should preserve both scene and display offsets")
        return False
    if restored.tz_label != "+8" or restored.display_tz_label != "-3":
        Logger.error(
            f"Serialized labels should remain canonical, got {restored.tz_label!r} and {restored.display_tz_label!r}"
        )
        return False
    return True


@func_case
async def test_timezone_offset(tester: Tester):
    """core.builtins.session.info: 时区偏移取值来源测试"""
    await tester.test(_test_offset_follows_target_data, "偏移量跟随场景设置测试")
    await tester.test(_test_core_default_used_when_target_unset, "场景未设置时跟随核心默认时区")
    await tester.test(_test_user_offset_only_affects_display, "用户时区仅影响展示")
    await tester.test(_test_invalid_target_offset_falls_back_to_core, "非法场景时区回退核心默认")
    await tester.test(_test_zero_offset_label, "零偏移标签规范化")
    await tester.test(_test_session_info_serialization_preserves_offsets, "会话序列化保留场景与显示偏移")

    return tester
