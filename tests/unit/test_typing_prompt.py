"""输入提示开关的取值来源测试。

``~setup typing`` 将开关写入用户数据（``sender_data``），故各处判断必须一律读用户数据。
曾有解析路径误读场景数据（``target_data``），而该键从不写入场景数据，导致判断恒取
默认值、用户关不掉输入提示。此处以行为断言与静态断言双重设防。
"""

from pathlib import Path

from core.builtins.session.info import SessionInfo
from core.database.models import SenderUnionInfo, TargetUnionInfo
from core.logger import Logger
from core.tester import func_case, Tester

# 判断须收敛到此属性，不得由各调用点自行读取原始键
SWITCH_KEY = "typing_prompt"
PARSER_PATH = Path("core/builtins/parser/message.py")


def _make_session(sender_data: dict | None, target_data: dict | None = None) -> SessionInfo:
    """构造一个带 union 数据的会话。

    :param sender_data: 用户数据；传 None 表示该会话没有用户 union（如主动推送）。
    :param target_data: 场景数据。
    :return: 可供取值判断的会话信息。
    """
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
    """用户未设置过该开关时，输入提示默认开启"""
    if not _make_session({}).typing_prompt_enabled:
        Logger.error("Typing prompt should be enabled by default")
        return False
    return True


def _test_switch_respects_user_setting() -> bool:
    """用户关闭该开关后，输入提示须随之关闭"""
    if _make_session({SWITCH_KEY: False}).typing_prompt_enabled:
        Logger.error("Typing prompt should follow the user setting stored in sender_data")
        return False
    return True


def _test_switch_ignores_target_data() -> bool:
    """场景数据不承载该开关，其中的同名键不得影响判断"""
    session = _make_session({SWITCH_KEY: False}, target_data={SWITCH_KEY: True})
    if session.typing_prompt_enabled:
        Logger.error("Typing prompt must be read from sender_data, not target_data")
        return False
    return True


def _test_switch_without_sender_union() -> bool:
    """没有用户 union 的会话无从得知其偏好，不显示输入提示"""
    if _make_session(None).typing_prompt_enabled:
        Logger.error("Sessions without a sender union should not show the typing prompt")
        return False
    return True


def _test_parser_reads_switch_through_session() -> bool:
    """解析器不得各自读取原始键，否则数据来源迟早再次读错"""
    source = PARSER_PATH.read_text(encoding="utf-8")
    # 只认作为字典键出现的字面量，属性名 typing_prompt_enabled 不在此列
    if f'"{SWITCH_KEY}"' in source or f"'{SWITCH_KEY}'" in source:
        Logger.error(
            f"{PARSER_PATH} still reads the raw {SWITCH_KEY!r} key; "
            "use SessionInfo.typing_prompt_enabled so the source stays in one place"
        )
        return False
    return True


@func_case
async def test_typing_prompt(tester: Tester):
    """core.builtins.session.info: 输入提示开关的取值来源测试"""
    await tester.test(_test_switch_defaults_to_enabled, "开关默认开启测试")
    await tester.test(_test_switch_respects_user_setting, "开关跟随用户设置测试")
    await tester.test(_test_switch_ignores_target_data, "开关不受场景数据影响测试")
    await tester.test(_test_switch_without_sender_union, "无用户 union 不提示测试")
    await tester.test(_test_parser_reads_switch_through_session, "解析器统一取值测试")

    return tester
