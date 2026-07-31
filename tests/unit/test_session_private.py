"""core.builtins.session 单元测试 - 私聊场景标识（需要数据库）。"""

from core.builtins.converter import converter
from core.builtins.session.info import SessionInfo
from core.tester import func_case, Tester


async def _test_is_private_defaults_to_false():
    """测试私聊标识 - 未指明时按非私聊处理"""
    try:
        session_info = await SessionInfo.assign(
            target_id="PRIV|Group|1", target_from="PRIV|Group", client_name="PRIV", create=True
        )
        return session_info.is_private is False

    except Exception:
        return False


async def _test_is_private_survives_serialization():
    """测试私聊标识 - 须能跨进程传递"""
    try:
        # 会话由 bot 进程构造、经队列送至 server 进程，标识不随序列化丢失才有意义
        session_info = await SessionInfo.assign(
            target_id="PRIV|Private|1",
            target_from="PRIV|Private",
            client_name="PRIV",
            is_private=True,
            create=True,
        )
        raw = converter.unstructure(session_info)
        return raw.get("is_private") is True and converter.structure(raw, SessionInfo).is_private is True

    except Exception:
        return False


@func_case
async def test_session_private(tester: Tester):
    """core.builtins.session.info: 私聊标识测试"""
    await tester.test(_test_is_private_defaults_to_false, "缺省为非私聊测试")
    await tester.test(_test_is_private_survives_serialization, "跨进程传递测试")

    return tester
