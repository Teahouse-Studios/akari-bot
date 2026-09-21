"""QQBot 指令操作标签的渲染测试。"""

from types import SimpleNamespace
from urllib.parse import quote

from bots.qqbot.context import (
    ACTION_TEXT_MAX_LENGTH,
    QQBOT_MAX_KEYBOARD_COLUMNS,
    QQBOT_MAX_KEYBOARD_ROWS,
    _build_qqbot_keyboard,
    _render_action_text,
)
from bots.qqbot.info import target_group_prefix
from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import ActionTextElement, ButtonFrameElement, ButtonRows, PlainElement
from core.builtins.message.internal import Button
from core.builtins.session.info import SessionInfo
from core.i18n import Locale
from core.tester import func_case, Tester
from core.utils.button_runtime import BUTTON_TOKEN_PREFIX, ButtonConsumeStatus, consume_button, _clear_button_registry


def _test_render_full_attributes():
    try:
        elem = ActionTextElement.assign("~wiki 沙盒", show="沙盒", reference=True).resolve(None)
        tag = _render_action_text(elem)
        expected = (
            f'<qqbot-cmd-input text="{quote("~wiki 沙盒", safe="")}" '
            f'show="{quote("沙盒", safe="")}" reference="true" />'
        )
        return tag == expected
    except Exception:
        return False


def _test_render_omits_empty_show():
    try:
        elem = ActionTextElement.assign("~wiki 沙盒").resolve(None)
        tag = _render_action_text(elem)
        if "show=" in tag:
            return False
        if 'reference="false"' not in tag:
            return False
        return True
    except Exception:
        return False


def _test_render_escapes_quotes():
    try:
        elem = ActionTextElement.assign('~echo "a" <b> &c', show="<标签>").resolve(None)
        tag = _render_action_text(elem)
        inner = tag[len("<qqbot-cmd-input ") : -len(" />")]
        for char in ('"a"', "<b>", "&c", "<标签>"):
            if char in inner:
                return False
        return True
    except Exception:
        return False


def _test_render_truncates_text():
    try:
        long_text = "长" * 200
        elem = ActionTextElement.assign(long_text).resolve(None)
        tag = _render_action_text(elem)
        expected = quote("长" * ACTION_TEXT_MAX_LENGTH, safe="")
        if f'text="{expected}"' not in tag:
            return False
        return True
    except Exception:
        return False


def _test_render_truncates_show():
    try:
        elem = ActionTextElement.assign("~wiki 沙盒", show="标" * 150).resolve(None)
        tag = _render_action_text(elem)
        expected = quote("标" * ACTION_TEXT_MAX_LENGTH, safe="")
        if f'show="{expected}"' not in tag:
            return False
        if f'text="{quote("~wiki 沙盒", safe="")}"' not in tag:
            return False
        return True
    except Exception:
        return False


def _test_render_empty_text():
    try:
        elem = ActionTextElement.assign("").resolve(None)
        return _render_action_text(elem) == ""
    except Exception:
        return False


def _test_send_msg_markdown_inline_join():
    try:
        # 复刻 send_msg_markdown() 的拼接逻辑，验证状态跟踪的取值
        elements = [
            PlainElement.assign("（"),
            ActionTextElement.assign("~wiki 沙盒").resolve(None),
            PlainElement.assign("）"),
        ]
        texts = []
        inline_pending = False
        for x in elements:
            if isinstance(x, ActionTextElement):
                tag = _render_action_text(x)
                if tag:
                    if texts:
                        texts[-1] += tag
                    else:
                        texts.append(tag)
                inline_pending = True
            else:
                if inline_pending and texts:
                    texts[-1] += x.text
                else:
                    texts.append(x.text)
                inline_pending = False
        if len(texts) != 1:
            return False
        if not texts[0].startswith("（<qqbot-cmd-input "):
            return False
        if not texts[0].endswith("/>）"):
            return False
        return True
    except Exception:
        return False


def _test_button_element_builds_keyboard():
    try:
        session = SessionInfo(
            target_id=f"{target_group_prefix}|1",
            target_from=target_group_prefix,
            client_name="QQBot",
            sender_id="QQBot|1",
            locale=Locale("zh_cn"),
            support_button=True,
        )
        sendable = MessageChain.assign(
            [Button("Docs", "https://example.com"), Button("Help", "~help", reply_id="callback-123")]
        ).as_sendable(session)
        frame = next(element for element in sendable if isinstance(element, ButtonFrameElement))
        _clear_button_registry()
        keyboard = _build_qqbot_keyboard(frame.rows, session, SimpleNamespace(scope="group"))
        docs, help_button = keyboard["content"]["rows"][0]["buttons"]
        return (
            docs["action"]["type"] == 0
            and docs["action"]["data"] == "https://example.com"
            and help_button["action"]["type"] == 1
            and "click_limit" not in help_button["action"]
            and help_button["action"]["data"].startswith(BUTTON_TOKEN_PREFIX)
            and (result := consume_button(help_button["action"]["data"], "QQBot|1")).status
            is ButtonConsumeStatus.SUCCESS
            and result.payload == "~help"
            and result.reply_id == "callback-123"
        )
    except Exception:
        return False


def _test_keyboard_reflows_and_caps_qq_limits():
    try:
        session = SessionInfo(
            target_id=f"{target_group_prefix}|1",
            target_from=target_group_prefix,
            client_name="QQBot",
            sender_id="QQBot|1",
            locale=Locale("zh_cn"),
            support_button=True,
        )
        rows = [ButtonRows.assign([Button(f"B{index}", str(index)) for index in range(57)])]
        keyboard = _build_qqbot_keyboard(rows, session, SimpleNamespace(scope="group"))
        rendered_rows = keyboard["content"]["rows"]
        rendered_buttons = [button for row in rendered_rows for button in row["buttons"]]
        return (
            len(rendered_rows) <= QQBOT_MAX_KEYBOARD_ROWS
            and all(len(row["buttons"]) <= QQBOT_MAX_KEYBOARD_COLUMNS for row in rendered_rows)
            and len(rendered_buttons) == QQBOT_MAX_KEYBOARD_ROWS * QQBOT_MAX_KEYBOARD_COLUMNS
            and rendered_buttons[-1]["render_data"]["label"] == "B49"
        )
    except Exception:
        return False


@func_case
async def test_qqbot_action_text(tester: Tester):
    """bots.qqbot.context: 指令操作标签渲染测试"""
    await tester.test(_test_render_full_attributes, "标签属性完整性测试")
    await tester.test(_test_render_omits_empty_show, "无 show 省略属性测试")
    await tester.test(_test_render_escapes_quotes, "属性值编码测试")
    await tester.test(_test_render_truncates_text, "text 截断测试")
    await tester.test(_test_render_truncates_show, "show 独立截断测试")
    await tester.test(_test_render_empty_text, "空 text 不产出标签测试")
    await tester.test(_test_send_msg_markdown_inline_join, "行内拼接测试")
    await tester.test(_test_button_element_builds_keyboard, "ButtonElement 构建键盘测试")
    await tester.test(_test_keyboard_reflows_and_caps_qq_limits, "QQBot 键盘行列限制测试")

    return tester
