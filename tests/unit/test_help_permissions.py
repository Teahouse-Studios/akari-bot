"""QQ 官方机器人权限快捷配置命令测试。"""

from types import SimpleNamespace

from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import ActionTextElement, I18NContextElement, URLElement
from core.constants.exceptions import SessionFinished
from core.i18n import Locale
from core.tester import func_case, Tester
from modules.core.help import qqbot_permissions


class _PermissionsSession:
    def __init__(self):
        self.session_info = SimpleNamespace(
            tmp={
                "qq_bot_uid": "uid-value",
                "qq_bot_qqnum": "987654",
            }
        )
        self.finished_message = None

    async def finish(self, message):
        self.finished_message = MessageChain.assign(message)
        raise SessionFinished


async def _test_qqbot_permissions_quick_config():
    msg = _PermissionsSession()
    try:
        await qqbot_permissions(msg, "123456")
    except SessionFinished:
        pass

    if not msg.finished_message or len(msg.finished_message.values) != 1:
        return False
    prompt = msg.finished_message.values[0]
    if not isinstance(prompt, I18NContextElement):
        return False
    if prompt.key != "core.message.help.qqbot.permissions.quick_config":
        return False

    url_chain = prompt.kwargs.get("url")
    if not isinstance(url_chain, MessageChain) or len(url_chain.values) != 1:
        return False
    url = url_chain.values[0]
    expected = (
        "https://club.vip.qq.com/transfer?open_kuikly_info=%7B%22page_name%22%3A%20%22"
        "ai_group_service_agreement_pop_page%22%2C%22groupCode%22%3A123456%2C%22"
        "botUin%22%3A987654%2C%22botUid%22%3A%22uid-value%22%2C%22screen%22%3A1%7D"
    )
    return isinstance(url, URLElement) and url.original_url == expected and url.trusted is True


async def _test_qqbot_permissions_prompts():
    locale = Locale("zh_cn")
    permissions = locale.t("core.message.help.qqbot.permissions", cmd="COMMAND")
    quick_config = locale.t("core.message.help.qqbot.permissions.quick_config", url="LINK")
    return (
        permissions.endswith("安卓手机可以输入 COMMAND来快速配置功能。")
        and quick_config == "使用安卓手机打开以下链接\nLINK"
    )


async def _test_qqbot_permissions_action_text():
    msg = _PermissionsSession()
    try:
        await qqbot_permissions(msg)
    except SessionFinished:
        pass

    if not msg.finished_message or len(msg.finished_message.values) != 1:
        return False
    prompt = msg.finished_message.values[0]
    if not isinstance(prompt, I18NContextElement):
        return False
    command = prompt.kwargs.get("cmd")
    return (
        isinstance(command, ActionTextElement)
        and command.text.text == "/help permissions "
        and command.show is not None
        and command.show.text == "/help permissions [<qq群号>]"
        and command.show_on_fallback is False
    )


async def _test_qqbot_permissions_rejects_placeholder():
    msg = _PermissionsSession()
    try:
        await qqbot_permissions(msg, "[<qq群号>]")
    except SessionFinished:
        pass

    if not msg.finished_message or len(msg.finished_message.values) != 1:
        return False
    prompt = msg.finished_message.values[0]
    return (
        isinstance(prompt, I18NContextElement) and prompt.key == "core.message.help.qqbot.permissions.invalid_group_id"
    )


@func_case
async def test_help_permissions(tester: Tester):
    await tester.test(_test_qqbot_permissions_quick_config, "QQ 官方机器人权限快捷配置链接")
    await tester.test(_test_qqbot_permissions_prompts, "QQ 官方机器人权限配置提示")
    await tester.test(_test_qqbot_permissions_action_text, "QQ 官方机器人权限配置 ActionText")
    await tester.test(_test_qqbot_permissions_rejects_placeholder, "QQ 官方机器人权限配置参数防呆")
    return tester
