"""Discord 按钮组件单元测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bots.discord.buttons import build_discord_button_view, disable_selected_button
from bots.discord.context import DiscordContextManager
from bots.discord.features import features
from core.builtins.session.info import SessionInfo
from core.tester import Tester, func_case
from core.utils.button_runtime import BUTTON_TOKEN_PREFIX, _clear_button_registry


def _view():
    _clear_button_registry()
    return build_discord_button_view([{"A": "~a", "B": "~b"}, {"C": "~c"}], "Discord|Client|1")


def _test_view_layout_and_tokens():
    view = _view()
    rows = [item.row for item in view.children]
    return (
        [item.label for item in view.children] == ["A", "B", "C"]
        and rows == [0, 0, 1]
        and all(item.custom_id.startswith(BUTTON_TOKEN_PREFIX) for item in view.children)
        and all(len(item.custom_id) <= 100 for item in view.children)
    )


def _test_disables_only_selected():
    view = _view()
    selected = view.children[1].custom_id
    changed = disable_selected_button(view, selected)
    return changed and [item.disabled for item in view.children] == [False, True, False]


def _test_platform_capacity():
    rows = [{f"B{row}-{column}": f"~b {row} {column}" for column in range(7)} for row in range(7)]
    view = build_discord_button_view(rows, "Discord|Client|1")
    return len(view.children) == 25 and all(0 <= item.row < 5 for item in view.children)


def _test_feature_enabled():
    return features.support_button is True


async def _test_interaction_native_permission_uses_clicking_user():
    user = SimpleNamespace(id=1)
    channel = SimpleNamespace(permissions_for=lambda member: SimpleNamespace(administrator=member is user))
    interaction = SimpleNamespace(channel=channel, user=user)
    session = SessionInfo(
        target_id="Discord|Channel|1",
        target_from="Discord|Channel",
        client_name="Discord",
        sender_id="Discord|Client|1",
        session_id="discord-permission-test",
    )
    DiscordContextManager.add_context(session, interaction)
    try:
        return await DiscordContextManager.check_native_permission(session)
    finally:
        DiscordContextManager.del_context(session)


async def _test_successful_click_routes_message():
    from bots.discord.interactions import handle_button_click

    _clear_button_registry()
    view = _view()
    button = view.children[0]
    response = SimpleNamespace(is_done=lambda: False, defer=AsyncMock())
    message = SimpleNamespace(id=10, edit=AsyncMock())
    interaction = SimpleNamespace(
        user=SimpleNamespace(id=1, name="tester"),
        channel=SimpleNamespace(id=20),
        message=message,
        response=response,
    )
    assigned = SimpleNamespace()
    with (
        patch("bots.discord.interactions.SessionInfo.assign", new=AsyncMock(return_value=assigned)) as assign,
        patch("bots.discord.interactions.Bot.process_message", new=AsyncMock()) as process,
        patch("bots.discord.interactions._get_bot_id", return_value="30"),
    ):
        await handle_button_click(interaction, button)
    kwargs = assign.await_args.kwargs
    return (
        response.defer.await_count == 1
        and message.edit.await_count == 1
        and button.disabled is True
        and kwargs["sender_id"] == "Discord|Client|1"
        and kwargs["reply_id"] == "10"
        and kwargs["messages"].to_str() == "~a"
        and process.await_count == 1
    )


async def _test_invalid_click_does_not_route_message():
    from bots.discord.interactions import handle_button_click

    _clear_button_registry()
    view = _view()
    button = view.children[0]
    response = SimpleNamespace(is_done=lambda: False, send_message=AsyncMock())
    interaction = SimpleNamespace(
        user=SimpleNamespace(id=2, name="other"),
        channel=SimpleNamespace(id=20),
        message=SimpleNamespace(id=10),
        response=response,
    )
    with patch("bots.discord.interactions.Bot.process_message", new=AsyncMock()) as process:
        await handle_button_click(interaction, button)
    return response.send_message.await_args.kwargs.get("ephemeral") is True and process.await_count == 0


@func_case
async def test_discord_buttons(tester: Tester):
    """Discord 按钮组件。"""
    await tester.test(_test_view_layout_and_tokens, "按钮布局与 token")
    await tester.test(_test_disables_only_selected, "仅停用当前按钮")
    await tester.test(_test_platform_capacity, "平台容量限制")
    await tester.test(_test_feature_enabled, "平台声明按钮能力")
    await tester.test(_test_interaction_native_permission_uses_clicking_user, "原生权限使用点击用户")
    await tester.test(_test_successful_click_routes_message, "合法点击回流消息")
    await tester.test(_test_invalid_click_does_not_route_message, "无效点击不回流消息")
    return tester
