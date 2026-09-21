"""时区偏移取值来源测试。"""

from datetime import timedelta

from core.builtins.session.info import SessionInfo
from core.logger import Logger
from core.tester import func_case, Tester

# 场景数据中承载时区偏移的键，写入方为 modules/core/setup.py
OFFSET_KEY = "timezone_offset"


async def _make_session(offset: str) -> SessionInfo:
    target_id = "TEST|Group|timezone_offset"
    session_info = await SessionInfo.assign(
        target_id=target_id,
        target_from="TEST|Group",
        client_name="TEST",
        sender_id="TEST|1",
    )
    await session_info.target_union_info.edit_target_data(OFFSET_KEY, offset)
    return await SessionInfo.assign(
        target_id=target_id,
        target_from="TEST|Group",
        client_name="TEST",
        sender_id="TEST|1",
    )


async def _test_offset_follows_target_data() -> bool:
    session_info = await _make_session("+5:30")
    if session_info.timezone_offset != timedelta(hours=5, minutes=30):
        Logger.error(f"Session should adopt the configured offset, got {session_info.timezone_offset}")
        return False
    if session_info._tz_offset != "+5:30":
        Logger.error(f"Session should keep the raw offset string, got {session_info._tz_offset!r}")
        return False
    return True


@func_case
async def test_timezone_offset(tester: Tester):
    """core.builtins.session.info: 时区偏移取值来源测试"""
    await tester.test(_test_offset_follows_target_data, "偏移量跟随场景设置测试")

    return tester
