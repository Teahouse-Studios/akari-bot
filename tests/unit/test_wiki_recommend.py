"""wiki 推荐绑定列表单元测试 - 按钮数据构造与发出门槛。"""

from unittest.mock import patch

from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import ButtonFrameElement, I18NContextElement
from core.builtins.session.features import Features
from core.builtins.session.info import SessionInfo
from core.builtins.session.internal import MessageSession
from core.builtins.utils import command_prefix
from core.constants.exceptions import SessionFinished
from core.tester import func_case, Tester
from core.utils.button import DEFAULT_BUTTONS_PER_ROW
from modules.wiki.utils.recommend import (
    RECOMMENDED_WIKIS,
    finish_with_start_wiki_not_set,
    get_recommend_button_data,
)


async def _probe(target_id: str, client_name: str, support_button: bool, is_admin: bool) -> dict:
    session_info = await SessionInfo.assign(
        target_id=target_id,
        target_from=f"{client_name}|Group",
        client_name=client_name,
        sender_id=f"{client_name}|1",
        features=Features(support_button=support_button),
    )
    msg = MessageSession(session_info=session_info)
    captured = {}

    async def _finish(self, message_chain=None, **kwargs):
        captured["prompts"] = MessageChain.assign(message_chain)
        raise SessionFinished

    async def _check_permission(self):
        return is_admin

    with (
        patch.object(MessageSession, "finish", _finish),
        patch.object(MessageSession, "check_permission", _check_permission),
    ):
        try:
            await finish_with_start_wiki_not_set(msg)
        except SessionFinished:
            pass
    return captured


async def _test_button_data_shape():
    try:
        rows = get_recommend_button_data()
        if len(rows) != 1:
            return False
        name, url = RECOMMENDED_WIKIS[0]
        return [(button.show, button.value) for button in rows[0].buttons] == [
            (name, f"{command_prefix[0]}wiki set {url}")
        ]

    except Exception:
        return False


async def _test_button_rows_are_split():
    try:
        count = DEFAULT_BUTTONS_PER_ROW * 2 + 1
        wikis = [(f"Wiki {i}", f"https://example{i}.invalid/api.php") for i in range(count)]
        with patch("modules.wiki.utils.recommend.RECOMMENDED_WIKIS", wikis):
            rows = get_recommend_button_data()
        # 7 个按钮在上限 3 之下分作三行，余数均摊到首行
        return [len(row.buttons) for row in rows] == [3, 2, 2]

    except Exception:
        return False


async def _test_button_prefix_reachable_from_interaction():
    try:
        # 与 bots/qqbot/bot.py 的 on_interaction_create 一致：不指定前缀，
        # 故会话取到的是全局配置的前缀，而非常规消息入口所用的斜杠前缀。
        session_info = await SessionInfo.assign(
            target_id="QQBot|Group|recommend_interaction",
            target_from="QQBot|Group",
            client_name="QQBot",
            sender_id="QQBot|1",
        )
        data = get_recommend_button_data()[0].buttons[0].value
        return any(data.startswith(prefix) for prefix in session_info.prefixes)

    except Exception:
        return False


async def _test_admin_gets_buttons():
    try:
        captured = await _probe("QQBot|Group|recommend_admin", "QQBot", True, True)
        keys = [element.key for element in captured["prompts"] if isinstance(element, I18NContextElement)]
        buttons = [element for element in captured["prompts"] if isinstance(element, ButtonFrameElement)]
        return (
            len(buttons) == 1
            and buttons[0].rows == get_recommend_button_data()
            and keys
            == [
                "wiki.message.set.not_set",
                "wiki.message.set.not_set.recommend",
            ]
        )

    except Exception:
        return False


async def _test_non_admin_gets_no_buttons():
    try:
        captured = await _probe("QQBot|Group|recommend_member", "QQBot", True, False)
        keys = [element.key for element in captured["prompts"] if isinstance(element, I18NContextElement)]
        return not captured["prompts"].contains(ButtonFrameElement) and keys == ["wiki.message.set.not_set"]

    except Exception:
        return False


async def _test_other_client_gets_buttons():
    try:
        captured = await _probe("TEST|Group|recommend_other", "TEST", True, True)
        keys = [element.key for element in captured["prompts"] if isinstance(element, I18NContextElement)]
        buttons = [element for element in captured["prompts"] if isinstance(element, ButtonFrameElement)]
        return (
            len(buttons) == 1
            and buttons[0].rows == get_recommend_button_data()
            and keys
            == [
                "wiki.message.set.not_set",
                "wiki.message.set.not_set.recommend",
            ]
        )

    except Exception:
        return False


async def _test_button_unsupported_gets_no_buttons():
    try:
        captured = await _probe("QQBot|Group|recommend_nobutton", "QQBot", False, True)
        keys = [element.key for element in captured["prompts"] if isinstance(element, I18NContextElement)]
        return not captured["prompts"].contains(ButtonFrameElement) and keys == ["wiki.message.set.not_set"]

    except Exception:
        return False


@func_case
async def test_wiki_recommend(tester: Tester):
    """wiki 推荐绑定列表：按钮数据与发出门槛测试"""
    await tester.test(_test_button_data_shape, "按钮数据结构测试")
    await tester.test(_test_button_rows_are_split, "按钮分行测试")
    await tester.test(_test_button_prefix_reachable_from_interaction, "按钮前缀可识别测试")
    await tester.test(_test_admin_gets_buttons, "管理员收到按钮测试")
    await tester.test(_test_non_admin_gets_no_buttons, "非管理员无按钮测试")
    await tester.test(_test_other_client_gets_buttons, "其他平台声明后有按钮测试")
    await tester.test(_test_button_unsupported_gets_no_buttons, "无按钮能力时无按钮测试")

    return tester
