"""「模块不存在」提示开关的测试。

用户输入了不存在的命令时，机器人会回一句「此模块不存在」。人多的群里这条提示颇为吵闹，
故允许场景管理员关掉它。关掉之后该场景对无效命令完全不作回应。

该提示原有两个发出点（拼写检查未命中、以及未开拼写检查时命令不在模块列表中），代码逐字
相同。此处一并收敛为一个函数，开关的判定才只有一处，不会改了一处漏了另一处。
"""

from pathlib import Path
from unittest.mock import patch

from core.builtins.parser.message import send_invalid_module_prompt
from core.builtins.session.info import SessionInfo
from core.builtins.session.internal import MessageSession
from core.database.models import SenderUnionInfo, TargetUnionInfo
from core.logger import Logger
from core.tester import func_case, Tester

# 场景数据中承载该开关的键
SWITCH_KEY = "invalid_module_prompt"
PARSER_PATH = Path("core/builtins/parser/message.py")
# 提示所用的多语言键，用于核对发出点的数量
PROMPT_KEY = "parser.command.invalid.module"


def _make_session(target_data: dict | None = None, sender_data: dict | None = None) -> SessionInfo:
    """构造一个带 union 数据的会话。

    :param target_data: 场景数据。
    :param sender_data: 用户数据。
    :return: 会话信息。
    """
    return SessionInfo(
        target_id="TEST|Group|invalid_module",
        sender_id="TEST|1",
        target_from="TEST|Group",
        client_name="TEST",
        session_id="invalid-module",
        target_union_info=TargetUnionInfo(union_id="UTID|1", target_data=target_data or {}),
        sender_union_info=SenderUnionInfo(union_id="USID|1", sender_data=sender_data or {}),
        prefixes=["~"],
    )


async def _capture(target_data: dict | None) -> list:
    """跑一遍提示的发出流程，取回它交给 send_message 的内容。

    :param target_data: 场景数据。
    :return: send_message 收到的消息链；未发送时为空列表。
    """
    msg = MessageSession(session_info=_make_session(target_data))
    sent = []

    async def _send_message(self, message_chain=None, **kwargs):
        sent.append(message_chain)

    with patch.object(MessageSession, "send_message", _send_message):
        await send_invalid_module_prompt(msg)
    return sent


def _test_switch_defaults_to_enabled() -> bool:
    """场景未设置过该开关时，提示照常发出"""
    if not _make_session().invalid_module_prompt_enabled:
        Logger.error("The invalid module prompt should be enabled by default")
        return False
    return True


def _test_switch_respects_target_setting() -> bool:
    """场景关闭该开关后，判定须随之为假"""
    if _make_session({SWITCH_KEY: False}).invalid_module_prompt_enabled:
        Logger.error("The prompt should follow the switch stored in target_data")
        return False
    return True


def _test_switch_ignores_sender_data() -> bool:
    """该开关是场景域的，用户数据中的同名键不得影响判定"""
    session = _make_session({SWITCH_KEY: False}, sender_data={SWITCH_KEY: True})
    if session.invalid_module_prompt_enabled:
        Logger.error("The switch must be read from target_data, not sender_data")
        return False
    return True


async def _test_prompt_sent_when_enabled() -> bool:
    """开启时确实发出提示"""
    sent = await _capture(None)
    if len(sent) != 1:
        Logger.error(f"An enabled prompt should be sent exactly once, got {len(sent)}")
        return False
    if getattr(sent[0], "key", None) != PROMPT_KEY:
        Logger.error(f"The prompt should use {PROMPT_KEY}, got {sent[0]!r}")
        return False
    return True


async def _test_prompt_silenced_when_disabled() -> bool:
    """关闭时一声不响，对无效命令完全不作回应"""
    sent = await _capture({SWITCH_KEY: False})
    if sent:
        Logger.error(f"A disabled prompt must not be sent at all, got {sent!r}")
        return False
    return True


def _test_parser_reads_switch_through_session() -> bool:
    """解析器不得各自读取原始键，否则数据来源迟早读错"""
    source = PARSER_PATH.read_text(encoding="utf-8")
    # 只认作为字典键出现的字面量，属性名 invalid_module_prompt_enabled 不在此列
    if f'"{SWITCH_KEY}"' in source or f"'{SWITCH_KEY}'" in source:
        Logger.error(
            f"{PARSER_PATH} still reads the raw {SWITCH_KEY!r} key; "
            "use SessionInfo.invalid_module_prompt_enabled so the source stays in one place"
        )
        return False
    return True


def _test_prompt_has_single_emission_point() -> bool:
    """提示只应由一处发出，开关的判定才不会漏网

    该提示原有两个逐字相同的发出点，收敛为一个函数后，此处守住不再散开。
    """
    source = PARSER_PATH.read_text(encoding="utf-8")
    count = source.count(f'"{PROMPT_KEY}"')
    if count != 1:
        Logger.error(f"{PROMPT_KEY} should be emitted from exactly one place, found {count}")
        return False
    return True


@func_case
async def test_invalid_module_prompt(tester: Tester):
    """core.builtins.parser: 「模块不存在」提示开关测试"""
    await tester.test(_test_switch_defaults_to_enabled, "开关默认开启测试")
    await tester.test(_test_switch_respects_target_setting, "开关跟随场景设置测试")
    await tester.test(_test_switch_ignores_sender_data, "开关不受用户数据影响测试")
    await tester.test(_test_prompt_sent_when_enabled, "开启时发出提示测试")
    await tester.test(_test_prompt_silenced_when_disabled, "关闭时静默测试")
    await tester.test(_test_parser_reads_switch_through_session, "解析器统一取值测试")
    await tester.test(_test_prompt_has_single_emission_point, "提示只有一处发出测试")

    return tester
