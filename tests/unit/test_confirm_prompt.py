"""确认提示文案选择单元测试。

快速确认有三条互不相干的途径：按钮随消息键盘下发、表情反应由机器人补加、戳一戳为 QQ 独有。
此前提示文案把三者嵌在 support_reaction 一个门槛之下，按钮分支便永远够不着——QQ 官方
机器人的 support_reaction 为假，而它恰恰是唯一支持按钮的平台，于是明明下发了确认按钮，
提示却只说「发送是」。各途径须依各自的能力标志分别判定。

按钮不受 quick_confirm 管辖：该配置控制的是表情反应的补加与戳一戳的响应，
而按钮在 bots/qqbot/context.py 中只看 wait_type，配置关闭时照样下发。
"""

from types import SimpleNamespace
from unittest.mock import patch

from core.builtins.session.internal import confirm_prompt_key
from core.tester import func_case, Tester


def _session(support_button: bool = False, support_reaction: bool = False, client_name: str = "TEST"):
    """构造仅承载判定所需三项的会话替身。

    :param support_button: 是否支持按钮。
    :param support_reaction: 是否支持表情反应。
    :param client_name: 客户端名，仅用于区分戳一戳。
    """
    return SimpleNamespace(
        support_button=support_button,
        support_reaction=support_reaction,
        client_name=client_name,
    )


def _test_button_takes_precedence():
    """具备按钮能力时提示点击按钮，且不被 support_reaction 为假所阻。"""
    return confirm_prompt_key(_session(support_button=True)) == "message.wait.confirm.prompt.button"


def _test_button_wins_over_reaction():
    """两种途径俱全时以按钮为准，按钮比表情反应更显眼。"""
    key = confirm_prompt_key(_session(support_button=True, support_reaction=True))
    return key == "message.wait.confirm.prompt.button"


def _test_qq_gets_poke_prompt():
    """QQ 的提示含戳一戳，为该平台独有。"""
    key = confirm_prompt_key(_session(support_reaction=True, client_name="QQ"))
    return key == "message.wait.confirm.prompt.qq"


def _test_other_reaction_client():
    """其余支持表情反应的平台用通用的表情反应提示。"""
    key = confirm_prompt_key(_session(support_reaction=True, client_name="Discord"))
    return key == "message.wait.confirm.prompt.reaction"


def _test_no_quick_path():
    """两种途径都不具备时只提示发送确认词。"""
    return confirm_prompt_key(_session()) == "message.wait.confirm.prompt"


def _test_quick_confirm_off_disables_reaction():
    """关闭快速确认后不再提示表情反应，与不补加反应的实际行为相符。"""
    with patch("core.builtins.session.internal.quick_confirm", False):
        key = confirm_prompt_key(_session(support_reaction=True, client_name="QQ"))
    return key == "message.wait.confirm.prompt"


def _test_quick_confirm_off_keeps_button():
    """关闭快速确认不影响按钮：平台照常下发，提示须如实告知。"""
    with patch("core.builtins.session.internal.quick_confirm", False):
        key = confirm_prompt_key(_session(support_button=True))
    return key == "message.wait.confirm.prompt.button"


@func_case
async def test_confirm_prompt(tester: Tester):
    """core: 确认提示文案的选择"""
    await tester.test(_test_button_takes_precedence, "按钮能力不受表情反应门槛所阻")
    await tester.test(_test_button_wins_over_reaction, "按钮优先于表情反应")
    await tester.test(_test_qq_gets_poke_prompt, "QQ 提示含戳一戳")
    await tester.test(_test_other_reaction_client, "其余平台用表情反应提示")
    await tester.test(_test_no_quick_path, "无快速途径时只提示确认词")
    await tester.test(_test_quick_confirm_off_disables_reaction, "关闭快速确认后不提示表情反应")
    await tester.test(_test_quick_confirm_off_keeps_button, "关闭快速确认不影响按钮提示")
    return tester
