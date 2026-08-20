"""按钮运行时单元测试。"""

from unittest.mock import patch

from core.builtins.utils import confirm_command_default
from core.tester import Tester, func_case
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import Button, ButtonFrame
from core.utils.button import bind_callback_reply_ids, build_button_rows
from core.utils.button_runtime import (
    BUTTON_TOKEN_PREFIX,
    ButtonConsumeStatus,
    _clear_button_registry,
    consume_button,
    normalize_button_payload,
    register_button_rows,
)


def _register(payload="~help", sender="Discord|Client|1"):
    _clear_button_registry()
    return register_button_rows(build_button_rows([{"Help": payload}]), sender)[0][0]


def _test_token_is_short_and_namespaced():
    button = _register()
    return button.token.startswith(BUTTON_TOKEN_PREFIX) and len(button.token.encode("utf-8")) < 64


def _test_callback_id_is_restored():
    button = _register("<q:callback-123>2")
    result = consume_button(button.token, "Discord|Client|1")
    return result.status is ButtonConsumeStatus.SUCCESS and result.payload == "2" and result.reply_id == "callback-123"


def _test_callback_reply_id_is_bound_semantically():
    chain = MessageChain.assign(
        ButtonFrame(build_button_rows([{"One": "1", "Docs": "https://example.com"}, {"Two": "2"}]))
    )
    reply_ids = bind_callback_reply_ids(chain, "virtual-reply")
    frame = chain.values[0]
    one, docs = frame.rows[0].buttons
    two = frame.rows[1].buttons[0]
    return (
        reply_ids == ["virtual-reply"]
        and one.reply_id == "virtual-reply"
        and two.reply_id == "virtual-reply"
        and docs.reply_id is None
        and one.value == "1"
    )


def _test_existing_button_reply_id_is_preserved():
    chain = MessageChain.assign([Button("Existing", "1", reply_id="existing"), Button("New", "2")])
    reply_ids = bind_callback_reply_ids(chain, "generated")
    existing, new = chain.values
    return reply_ids == ["existing", "generated"] and existing.reply_id == "existing" and new.reply_id == "generated"


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
    rows = register_button_rows(build_button_rows([{"A": "~a", "B": "~b"}]), "Discord|Client|1")
    first = consume_button(rows[0][0].token, "Discord|Client|1")
    sibling = consume_button(rows[0][1].token, "Discord|Client|1")
    return first.status is ButtonConsumeStatus.SUCCESS and sibling.status is ButtonConsumeStatus.SUCCESS


def _test_urls_do_not_register_tokens():
    _clear_button_registry()
    buttons = register_button_rows(
        build_button_rows([{"HTTP": "http://example.com", "HTTPS": "https://example.com", "Command": "~help"}]),
        "Discord|Client|1",
    )[0]
    return (
        buttons[0].url == "http://example.com"
        and buttons[0].token is None
        and buttons[1].url == "https://example.com"
        and buttons[1].token is None
        and buttons[2].url is None
        and buttons[2].token.startswith(BUTTON_TOKEN_PREFIX)
        and consume_button(buttons[2].token, "Discord|Client|1").status is ButtonConsumeStatus.SUCCESS
    )


def _test_register_prunes_expired_tokens():
    _clear_button_registry()
    with patch("core.utils.button_runtime.time.time", return_value=0.001):
        expired = register_button_rows(build_button_rows([{"Old": "~old"}]), "Discord|Client|1")[0][0]
    with patch("core.utils.button_runtime.time.time", return_value=7200.002):
        register_button_rows(build_button_rows([{"New": "~new"}]), "Discord|Client|1")
    return consume_button(expired.token, "Discord|Client|1", now=7200.002).status is ButtonConsumeStatus.INVALID


def _test_confirmation_payloads_are_normalized():
    yes = normalize_button_payload("confirm_yes")
    no = normalize_button_payload("confirm_no")
    unchanged = normalize_button_payload("~help")
    return yes == confirm_command_default[0] and no == "no" and unchanged == "~help"


@func_case
async def test_button_runtime(tester: Tester):
    """core.utils.button_runtime: 按钮运行时。"""
    await tester.test(_test_token_is_short_and_namespaced, "按钮 token 长度与命名空间")
    await tester.test(_test_callback_id_is_restored, "callback ID 拆分与恢复")
    await tester.test(_test_callback_reply_id_is_bound_semantically, "callback 虚拟回复 ID 语义绑定")
    await tester.test(_test_existing_button_reply_id_is_preserved, "保留按钮显式回复 ID")
    await tester.test(_test_forbidden_does_not_consume, "无权限点击不消费按钮")
    await tester.test(_test_second_use_is_rejected, "按钮只能成功使用一次")
    await tester.test(_test_expired_is_distinct_from_invalid, "过期与无效状态可区分")
    await tester.test(_test_consuming_one_button_keeps_sibling, "消费当前按钮不影响同组按钮")
    await tester.test(_test_urls_do_not_register_tokens, "HTTP 链接不注册 token")
    await tester.test(_test_register_prunes_expired_tokens, "注册时清理过期 token")
    await tester.test(_test_confirmation_payloads_are_normalized, "确认按钮 payload 归一化")
    return tester
