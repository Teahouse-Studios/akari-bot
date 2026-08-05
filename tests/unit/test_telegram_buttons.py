"""Telegram 按钮组件单元测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aiogram.types import InlineKeyboardMarkup

from bots.telegram.buttons import (
    build_telegram_button_markup,
    get_telegram_context_chat_and_user,
    remove_selected_button,
)
from bots.telegram.action_text import (
    build_action_text_inline_results,
    can_use_inline_action_text,
    is_own_inline_message,
)
from bots.telegram.features import features
from core.builtins.message.internal import ActionText
from core.tester import Tester, func_case
from core.utils.button_runtime import BUTTON_TOKEN_PREFIX, _clear_button_registry


def _markup():
    _clear_button_registry()
    return build_telegram_button_markup([{"A": "~a", "B": "~b"}, {"C": "~c"}], "Telegram|User|1")


def _test_markup_layout_and_tokens():
    markup = _markup()
    flat = [button for row in markup.inline_keyboard for button in row]
    return (
        [[button.text for button in row] for row in markup.inline_keyboard] == [["A", "B"], ["C"]]
        and all(button.callback_data.startswith(BUTTON_TOKEN_PREFIX) for button in flat)
        and all(len(button.callback_data.encode("utf-8")) <= 64 for button in flat)
    )


def _test_removes_only_selected_and_empty_row():
    markup = _markup()
    selected = markup.inline_keyboard[1][0].callback_data
    updated = remove_selected_button(markup, selected)
    return [[button.text for button in row] for row in updated.inline_keyboard] == [["A", "B"]]


def _test_removing_last_button_returns_none():
    markup = build_telegram_button_markup([{"A": "~a"}], "Telegram|User|1")
    selected = markup.inline_keyboard[0][0].callback_data
    return remove_selected_button(markup, selected) is None


def _test_feature_enabled():
    return features.support_button is True and features.support_action_text is True


def _test_action_text_uses_inline_query():
    markup = build_telegram_button_markup(
        [],
        "Telegram|User|1",
        action_texts=[ActionText("~help ", show="帮助")],
        supports_inline_queries=True,
    )
    button = markup.inline_keyboard[0][0]
    return button.text == "~help " and button.switch_inline_query_current_chat == "~help " and button.copy_text is None


def _test_action_text_falls_back_to_copy():
    markup = build_telegram_button_markup(
        [],
        "Telegram|User|1",
        action_texts=[ActionText("~help ", show="帮助")],
        supports_inline_queries=False,
    )
    button = markup.inline_keyboard[0][0]
    return (
        button.text == "~help "
        and button.switch_inline_query_current_chat is None
        and button.copy_text.text == "~help "
    )


def _test_inline_query_result_sends_edited_text():
    results = build_action_text_inline_results("~help edited")
    return (
        len(results) == 1
        and results[0].input_message_content.message_text == "~help edited"
        and results[0].input_message_content.parse_mode is None
    )


def _test_own_inline_message_detection():
    own = SimpleNamespace(via_bot=SimpleNamespace(id=1))
    other = SimpleNamespace(via_bot=SimpleNamespace(id=2))
    plain = SimpleNamespace(via_bot=None)
    return is_own_inline_message(own, 1) and not is_own_inline_message(other, 1) and not is_own_inline_message(plain, 1)


def _test_channel_uses_copy_fallback():
    return can_use_inline_action_text("Telegram|Group", True) and not can_use_inline_action_text(
        "Telegram|Channel", True
    )


def _test_callback_native_permission_uses_clicking_user():
    user = SimpleNamespace(id=1)
    chat = SimpleNamespace(id=20, type="group")
    callback = SimpleNamespace(from_user=user, message=SimpleNamespace(chat=chat))
    resolved_chat, resolved_user = get_telegram_context_chat_and_user(callback)
    return resolved_chat is chat and resolved_user is user


async def _test_successful_callback_routes_message():
    from bots.telegram.interactions import handle_button_callback

    _clear_button_registry()
    markup = _markup()
    callback_data = markup.inline_keyboard[0][0].callback_data
    message = SimpleNamespace(
        message_id=10,
        chat=SimpleNamespace(id=20, type="group"),
        reply_markup=markup,
        edit_reply_markup=AsyncMock(),
    )
    callback = SimpleNamespace(
        data=callback_data,
        from_user=SimpleNamespace(id=1, username="tester"),
        message=message,
        answer=AsyncMock(),
    )
    assigned = SimpleNamespace()
    with (
        patch("bots.telegram.interactions.SessionInfo.assign", new=AsyncMock(return_value=assigned)) as assign,
        patch("bots.telegram.interactions.Bot.process_message", new=AsyncMock()) as process,
        patch("bots.telegram.interactions._get_bot_id", return_value="30"),
    ):
        await handle_button_callback(callback)
    kwargs = assign.await_args.kwargs
    updated: InlineKeyboardMarkup = message.edit_reply_markup.await_args.kwargs["reply_markup"]
    return (
        callback.answer.await_count == 1
        and [[button.text for button in row] for row in updated.inline_keyboard] == [["B"], ["C"]]
        and kwargs["sender_id"] == "Telegram|User|1"
        and kwargs["message_id"] == "10"
        and kwargs["reply_id"] == "10"
        and kwargs["messages"].to_str() == "~a"
        and process.await_count == 1
    )


async def _test_callback_without_message_is_rejected():
    from bots.telegram.interactions import handle_button_callback

    callback = SimpleNamespace(
        data="akb:missing",
        from_user=SimpleNamespace(id=1),
        message=None,
        answer=AsyncMock(),
    )
    with patch("bots.telegram.interactions.Bot.process_message", new=AsyncMock()) as process:
        await handle_button_callback(callback)
    return callback.answer.await_count == 1 and process.await_count == 0


async def _test_forbidden_callback_does_not_route_message():
    from bots.telegram.interactions import handle_button_callback

    _clear_button_registry()
    markup = _markup()
    callback = SimpleNamespace(
        data=markup.inline_keyboard[0][0].callback_data,
        from_user=SimpleNamespace(id=2),
        message=SimpleNamespace(message_id=10, chat=SimpleNamespace(id=20, type="group")),
        answer=AsyncMock(),
    )
    with patch("bots.telegram.interactions.Bot.process_message", new=AsyncMock()) as process:
        await handle_button_callback(callback)
    return callback.answer.await_count == 1 and process.await_count == 0


async def _test_unrelated_callback_is_ignored():
    from bots.telegram.interactions import handle_button_callback

    callback = SimpleNamespace(data="other:callback", answer=AsyncMock())
    with patch("bots.telegram.interactions.Bot.process_message", new=AsyncMock()) as process:
        await handle_button_callback(callback)
    return callback.answer.await_count == 0 and process.await_count == 0


async def _test_inline_query_handler_answers_personally_without_cache():
    from bots.telegram.action_text import handle_action_text_inline_query

    inline_query = SimpleNamespace(query="~help edited", answer=AsyncMock())
    await handle_action_text_inline_query(inline_query)
    kwargs = inline_query.answer.await_args.kwargs
    results = inline_query.answer.await_args.args[0]
    return (
        kwargs == {"cache_time": 0, "is_personal": True}
        and results[0].input_message_content.message_text == "~help edited"
    )


@func_case
async def test_telegram_buttons(tester: Tester):
    """Telegram 按钮组件。"""
    await tester.test(_test_markup_layout_and_tokens, "按钮布局与 token")
    await tester.test(_test_removes_only_selected_and_empty_row, "仅移除当前按钮并清理空行")
    await tester.test(_test_removing_last_button_returns_none, "移除最后按钮后清空键盘")
    await tester.test(_test_feature_enabled, "平台声明按钮能力")
    await tester.test(_test_action_text_uses_inline_query, "ActionText 使用当前聊天 Inline Query")
    await tester.test(_test_action_text_falls_back_to_copy, "未启用 Inline Mode 时复制命令")
    await tester.test(_test_inline_query_result_sends_edited_text, "Inline Query 结果发送编辑后文本")
    await tester.test(_test_own_inline_message_detection, "识别当前机器人代发消息")
    await tester.test(_test_channel_uses_copy_fallback, "频道场景使用复制降级")
    await tester.test(_test_callback_native_permission_uses_clicking_user, "原生权限使用点击用户")
    await tester.test(_test_successful_callback_routes_message, "合法点击回流消息")
    await tester.test(_test_callback_without_message_is_rejected, "无聊天上下文时拒绝点击")
    await tester.test(_test_forbidden_callback_does_not_route_message, "无权限点击不回流消息")
    await tester.test(_test_unrelated_callback_is_ignored, "忽略非按钮回调")
    await tester.test(_test_inline_query_handler_answers_personally_without_cache, "Inline Query 不缓存且仅用户可见")
    return tester
