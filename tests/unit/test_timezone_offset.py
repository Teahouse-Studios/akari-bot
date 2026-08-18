"""时区偏移取值来源测试。

``~setup timeoffset`` 将偏移量写入场景数据的 timezone_offset 键，会话应读取同一份数据。
"""

from datetime import timedelta

from core.builtins.session.info import SessionInfo
from core.logger import Logger
from core.tester import func_case, Tester

# 场景数据中承载时区偏移的键，写入方为 modules/core/setup.py
OFFSET_KEY = "timezone_offset"


async def _make_session(offset: str) -> SessionInfo:
    """建立一个带指定时区偏移的会话。

    须经 assign() 而非直接构造：时区的解析发生在 assign() 中，直接构造得不到它。
    先建一次会话是为了拿到场景 union 以写入数据，再建一次才能读到写入后的取值。

    :param offset: 写入场景数据的时区偏移量。
    :return: 会话信息。
    """
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
    """场景设置的偏移量须反映到会话上，否则 setup timeoffset 形同虚设"""
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
