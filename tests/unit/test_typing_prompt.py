"""输入提示开关的取值来源测试。"""

from core.builtins.session.info import SessionInfo
from core.database.models import SenderUnionInfo, TargetUnionInfo
from core.logger import Logger
from core.tester import func_case, Tester

SWITCH_KEY = "typing_prompt"


def _make_session(sender_data: dict | None, target_data: dict | None = None) -> SessionInfo:
    return SessionInfo(
        target_id="QQ|Group|1",
        sender_id="QQ|Tiny|1",
        target_from="QQ|Group",
        client_name="QQ",
        session_id="typing-switch",
        target_union_info=TargetUnionInfo(union_id="UTID|1", target_data=target_data or {}),
        sender_union_info=(
            None if sender_data is None else SenderUnionInfo(union_id="USID|1", sender_data=sender_data)
        ),
    )


def _test_switch_defaults_to_enabled() -> bool:
    if not _make_session({}).typing_prompt_enabled:
        Logger.error("Typing prompt should be enabled by default")
        return False
    return True


def _test_switch_respects_user_setting() -> bool:
    if _make_session({SWITCH_KEY: False}).typing_prompt_enabled:
        Logger.error("Typing prompt should follow the user setting stored in sender_data")
        return False
    return True


def _test_switch_ignores_target_data() -> bool:
    session = _make_session({SWITCH_KEY: False}, target_data={SWITCH_KEY: True})
    if session.typing_prompt_enabled:
        Logger.error("Typing prompt must be read from sender_data, not target_data")
        return False
    return True


def _test_switch_without_sender_union() -> bool:
    if _make_session(None).typing_prompt_enabled:
        Logger.error("Sessions without a sender union should not show the typing prompt")
        return False
    return True


@func_case
async def test_typing_prompt(tester: Tester):
    """core.builtins.session.info: 输入提示开关的取值来源测试"""
    await tester.test(_test_switch_defaults_to_enabled, "开关默认开启测试")
    await tester.test(_test_switch_respects_user_setting, "开关跟随用户设置测试")
    await tester.test(_test_switch_ignores_target_data, "开关不受场景数据影响测试")
    await tester.test(_test_switch_without_sender_union, "无用户 union 不提示测试")

    return tester
