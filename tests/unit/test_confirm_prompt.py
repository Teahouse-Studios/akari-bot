"""确认提示文案选择单元测试。"""

from types import SimpleNamespace
from unittest.mock import patch

from core.builtins.session.internal import confirm_prompt_key
from core.tester import func_case, Tester


def _session(support_button: bool = False, support_reaction: bool = False, client_name: str = "TEST"):
    return SimpleNamespace(
        support_button=support_button,
        support_reaction=support_reaction,
        client_name=client_name,
    )


def _test_button_takes_precedence():
    return confirm_prompt_key(_session(support_button=True)) == "message.wait.confirm.prompt.button"


def _test_button_wins_over_reaction():
    key = confirm_prompt_key(_session(support_button=True, support_reaction=True))
    return key == "message.wait.confirm.prompt.button"


def _test_qq_gets_poke_prompt():
    key = confirm_prompt_key(_session(support_reaction=True, client_name="QQ"))
    return key == "message.wait.confirm.prompt.qq"


def _test_other_reaction_client():
    key = confirm_prompt_key(_session(support_reaction=True, client_name="Discord"))
    return key == "message.wait.confirm.prompt.reaction"


def _test_no_quick_path():
    return confirm_prompt_key(_session()) == "message.wait.confirm.prompt"


def _test_quick_confirm_off_disables_reaction():
    with patch("core.builtins.session.internal.quick_confirm", False):
        key = confirm_prompt_key(_session(support_reaction=True, client_name="QQ"))
    return key == "message.wait.confirm.prompt"


def _test_quick_confirm_off_keeps_button():
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
