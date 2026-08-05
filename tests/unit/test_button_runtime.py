"""按钮运行时单元测试。"""

from types import SimpleNamespace
from unittest.mock import patch

from core.builtins.utils import confirm_command_default
from core.i18n import Locale
from core.tester import Tester, func_case
from core.utils.button_runtime import (
    BUTTON_TOKEN_PREFIX,
    ButtonConsumeStatus,
    _clear_button_registry,
    consume_button,
    get_session_button_data,
    normalize_button_payload,
    register_button_rows,
)


def _register(payload="~help", sender="Discord|Client|1"):
    _clear_button_registry()
    return register_button_rows([{"Help": payload}], sender)[0][0]


def _test_token_is_short_and_namespaced():
    button = _register()
    return button.token.startswith(BUTTON_TOKEN_PREFIX) and len(button.token.encode("utf-8")) < 64


def _test_callback_id_is_restored():
    button = _register("<q:callback-123>2")
    result = consume_button(button.token, "Discord|Client|1")
    return result.status is ButtonConsumeStatus.SUCCESS and result.payload == "2" and result.reply_id == "callback-123"


def _test_forbidden_does_not_consume():
    button = _register()
    denied = consume_button(button.token, "Discord|Client|2")
    allowed = consume_button(button.token, "Discord|Client|1")
    return denied.status is ButtonConsumeStatus.FORBIDDEN and allowed.status is ButtonConsumeStatus.SUCCESS


def _test_second_use_is_rejected():
    button = _register()
    first = consume_button(button.token, "Discord|Client|1")
    second = consume_button(button.token, "Discord|Client|1")
    return first.status is ButtonConsumeStatus.SUCCESS and second.status is ButtonConsumeStatus.USED


def _test_expired_is_distinct_from_invalid():
    with patch("core.utils.button_runtime.time.time", return_value=0.001):
        button = _register()
    expired = consume_button(button.token, "Discord|Client|1", now=3600.002)
    invalid = consume_button(f"{BUTTON_TOKEN_PREFIX}missing", "Discord|Client|1")
    return expired.status is ButtonConsumeStatus.EXPIRED and invalid.status is ButtonConsumeStatus.INVALID


def _test_consuming_one_button_keeps_sibling():
    _clear_button_registry()
    rows = register_button_rows([{"A": "~a", "B": "~b"}], "Discord|Client|1")
    first = consume_button(rows[0][0].token, "Discord|Client|1")
    sibling = consume_button(rows[0][1].token, "Discord|Client|1")
    return first.status is ButtonConsumeStatus.SUCCESS and sibling.status is ButtonConsumeStatus.SUCCESS


def _test_register_prunes_expired_tokens():
    _clear_button_registry()
    with patch("core.utils.button_runtime.time.time", return_value=0.001):
        expired = register_button_rows([{"Old": "~old"}], "Discord|Client|1")[0][0]
    with patch("core.utils.button_runtime.time.time", return_value=7200.002):
        register_button_rows([{"New": "~new"}], "Discord|Client|1")
    return consume_button(expired.token, "Discord|Client|1", now=7200.002).status is ButtonConsumeStatus.INVALID


def _test_confirmation_payloads_are_normalized():
    yes = normalize_button_payload("confirm_yes")
    no = normalize_button_payload("confirm_no")
    unchanged = normalize_button_payload("~help")
    return yes == confirm_command_default[0] and no == "no" and unchanged == "~help"


def _test_wait_confirm_builds_buttons():
    session = SimpleNamespace(
        tmp={"wait_type": "wait_confirm", "wait_active": "yes"},
        locale=Locale("zh_cn"),
    )
    return get_session_button_data(session) == [
        {session.locale.t("message.yes"): "confirm_yes", session.locale.t("message.no"): "confirm_no"}
    ]


def _test_wait_choices_override_explicit_buttons():
    session = SimpleNamespace(
        tmp={
            "button_data": '[{"Explicit":"~explicit"}]',
            "wait_type": "wait_next_message",
            "wait_active": "yes",
            "wait_possibly_choices": '[{"Choice":"1"}]',
        },
        locale=Locale("zh_cn"),
    )
    return get_session_button_data(session) == [{"Choice": "1"}]


@func_case
async def test_button_runtime(tester: Tester):
    """core.utils.button_runtime: 按钮运行时。"""
    await tester.test(_test_token_is_short_and_namespaced, "按钮 token 长度与命名空间")
    await tester.test(_test_callback_id_is_restored, "callback ID 拆分与恢复")
    await tester.test(_test_forbidden_does_not_consume, "无权限点击不消费按钮")
    await tester.test(_test_second_use_is_rejected, "按钮只能成功使用一次")
    await tester.test(_test_expired_is_distinct_from_invalid, "过期与无效状态可区分")
    await tester.test(_test_consuming_one_button_keeps_sibling, "消费当前按钮不影响同组按钮")
    await tester.test(_test_register_prunes_expired_tokens, "注册时清理过期 token")
    await tester.test(_test_confirmation_payloads_are_normalized, "确认按钮 payload 归一化")
    await tester.test(_test_wait_confirm_builds_buttons, "等待确认生成按钮")
    await tester.test(_test_wait_choices_override_explicit_buttons, "等待选项优先于显式按钮")
    return tester
