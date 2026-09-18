"""统一机器人场景状态接口测试。"""

import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from core.builtins.session.bot_state import BotState
from core.builtins.session.context import ContextManager
from core.builtins.session.info import SessionInfo
from core.queue import codec
from core.queue.contracts import PlatformAPI
from core.tester import Tester, func_case


def _test_bot_state_is_serializable_and_preserves_unknown_permissions() -> bool:
    state = BotState(
        available=True,
        joined=True,
        permissions={"role": "admin", "bitset": 4, "custom": None},
        raw={"platform_field": ["value"]},
    )
    restored = codec.decode(codec.encode(state, BotState), BotState)
    return (
        restored == state
        and restored.has_permission("custom") is None
        and restored.has_permission("missing") is None
        and restored.has_permission("role") is None
    )


def _test_bot_state_rpc_contract_matches_context() -> bool:
    return PlatformAPI.check_bot_state.signature == inspect.signature(ContextManager.check_bot_state)


async def _test_webui_reports_full_state() -> bool:
    from bots.web.context import WebContextManager

    session = SessionInfo(
        target_id="Web|Group|state",
        target_from="Web|Group",
        client_name="Web",
        session_id="bot-state-web",
    )
    state = await WebContextManager.check_bot_state(session)
    return all(
        getattr(state, name) is True
        for name in (
            "available",
            "joined",
            "is_owner",
            "is_admin",
            "can_read_messages",
            "can_read_all_messages",
            "can_send_messages",
            "can_send_proactive_messages",
            "can_manage_messages",
            "can_manage_members",
            "can_restrict_members",
            "can_react",
            "can_send_private_messages",
        )
    )


async def _test_mock_session_provides_local_bot_state() -> bool:
    from core.tester.mock.session import MockMessageSession

    session = MockMessageSession()
    session.session_info = SessionInfo(
        target_id="TEST|Console|0",
        target_from="TEST",
        client_name="TEST",
        support_manage=True,
        support_reaction=True,
        support_private_msg=True,
    )
    state = await session.check_bot_state()
    return state.raw == {"platform": "test"} and state.can_manage_members and state.can_react


async def _test_discord_permission_state_maps_effective_channel_permissions() -> bool:
    import discord
    import bots.discord.context as discord_context

    DiscordContextManager = discord_context.DiscordContextManager

    permissions = discord.Permissions(
        view_channel=True,
        read_message_history=True,
        send_messages=True,
        manage_messages=True,
        moderate_members=True,
        add_reactions=True,
    )
    member = type("Member", (), {"id": 42, "guild_permissions": permissions})()
    guild = type("Guild", (), {"id": 7, "owner_id": 99, "me": member})()
    channel = type(
        "Channel",
        (),
        {"id": 8, "guild": guild, "permissions_for": lambda self, _: permissions},
    )()
    bot_user = type("User", (), {"id": 42})()
    session = SessionInfo(
        target_id="Discord|Channel|8",
        target_from="Discord|Channel",
        client_name="Discord",
        session_id="bot-state-discord",
    )
    with (
        patch.object(DiscordContextManager, "context", {session.session_id: type("Ctx", (), {"channel": channel})()}),
        patch.object(discord_context, "discord_bot", SimpleNamespace(user=bot_user)),
    ):
        state = await DiscordContextManager.check_bot_state(session)
    return (
        state.available is True
        and state.can_read_messages is True
        and state.can_manage_messages is True
        and state.can_restrict_members is True
        and state.permissions["moderate_members"] is True
    )


async def _test_qqbot_group_state_maps_official_bot_state() -> bool:
    import bots.qqbot.context as qqbot_context
    from bots.qqbot.info import target_group_prefix

    session = SessionInfo(
        target_id=f"{target_group_prefix}|group-openid",
        target_from=target_group_prefix,
        client_name="QQBot",
        session_id="bot-state-qqbot-group",
    )
    state_api = SimpleNamespace(
        get_group_bot_state=AsyncMock(
            return_value={
                "member_openid": "bot-openid",
                "joined_at": "2025-06-15T14:30:00+08:00",
                "allow_proactive_msg": False,
                "recv_msg_setting": "only_mention",
                "member_role": "admin",
            }
        )
    )
    with patch.object(qqbot_context, "_get_client", return_value=SimpleNamespace(api=state_api)):
        state = await qqbot_context.QQBotContextManager.check_bot_state(session)
    return (
        state.joined is True
        and state.is_admin is True
        and state.can_read_messages is True
        and state.can_read_all_messages is False
        and state.can_send_proactive_messages is False
        and state.permissions["allow_proactive_msg"] is False
        and state.raw["member_openid"] == "bot-openid"
    )


async def _test_non_web_private_context_does_not_claim_management_permissions() -> bool:
    import bots.qqbot.context as qqbot_context
    from bots.qqbot.info import target_c2c_prefix

    session = SessionInfo(
        target_id=f"{target_c2c_prefix}|user-openid",
        target_from=target_c2c_prefix,
        client_name="QQBot",
        session_id="bot-state-qqbot-private",
    )
    state = await qqbot_context.QQBotContextManager.check_bot_state(session)
    return (
        state.joined is True
        and state.can_send_messages is True
        and state.can_send_private_messages is True
        and state.is_owner is None
        and state.is_admin is None
        and state.can_manage_messages is None
        and state.can_manage_members is None
        and state.can_restrict_members is None
    )


async def _test_onebot_group_state_maps_bot_role() -> bool:
    import bots.onebot.context as onebot_context
    from bots.onebot.info import target_group_prefix

    session = SessionInfo(
        target_id=f"{target_group_prefix}|123",
        target_from=target_group_prefix,
        client_name="QQ",
        bot_id="456",
        session_id="bot-state-onebot-group",
    )
    call_action = AsyncMock(return_value={"user_id": 456, "role": "admin", "nickname": "Akari"})
    with patch.object(onebot_context.aiocqhttp_bot, "call_action", new=call_action):
        state = await onebot_context.OneBotContextManager.check_bot_state(session)
    return (
        state.joined is True
        and state.is_admin is True
        and state.is_owner is False
        and state.can_restrict_members is True
        and state.permissions["role"] == "admin"
        and call_action.await_args.kwargs == {"group_id": 123, "user_id": 456}
    )


async def _test_matrix_power_levels_map_to_common_permissions() -> bool:
    import nio
    import bots.matrix.context as matrix_context
    from bots.matrix.info import target_prefix

    session = SessionInfo(
        target_id=f"{target_prefix}|!room:test",
        target_from=target_prefix,
        client_name="Matrix",
        session_id="bot-state-matrix",
    )
    member = nio.RoomGetStateEventResponse({"membership": "join"}, "m.room.member", "@bot:test", "!room:test")
    power_levels = nio.RoomGetStateEventResponse(
        {
            "users": {"@bot:test": 60},
            "events": {"m.room.message": 10, "m.reaction": 20},
            "redact": 50,
            "ban": 50,
            "kick": 50,
            "invite": 0,
        },
        "m.room.power_levels",
        "",
        "!room:test",
    )
    client = SimpleNamespace(user_id="@bot:test", room_get_state_event=AsyncMock(side_effect=[member, power_levels]))
    with patch.object(matrix_context, "matrix_bot", client):
        state = await matrix_context.MatrixContextManager.check_bot_state(session)
    return (
        state.joined is True
        and state.is_admin is True
        and state.can_send_messages is True
        and state.can_manage_messages is True
        and state.can_restrict_members is True
        and state.permissions["power_level"] == 60
    )


async def _test_telegram_chat_member_status_uses_enum_value() -> bool:
    import importlib

    from aiogram.enums import ChatMemberStatus
    from bots.telegram.config import AiogramConfig, AiogramSecretConfig

    with (
        patch.object(AiogramConfig, "enable", False, create=True),
        patch.object(
            AiogramSecretConfig,
            "telegram_token",
            "123456:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij",
            create=True,
        ),
    ):
        telegram_context = importlib.import_module("bots.telegram.context")
    session = SessionInfo(
        target_id="Telegram|Group|-10001",
        target_from="Telegram|Group",
        client_name="Telegram",
        session_id="bot-state-telegram",
    )
    member = SimpleNamespace(
        status=ChatMemberStatus.ADMINISTRATOR,
        can_delete_messages=True,
        can_restrict_members=True,
        can_promote_members=False,
        model_dump=lambda mode: {"status": "administrator"},
    )
    with (
        patch.object(
            telegram_context.aiogram_bot,
            "get_chat",
            new=AsyncMock(return_value=SimpleNamespace(id=-10001, type="group")),
        ),
        patch.object(telegram_context.aiogram_bot, "me", new=AsyncMock(return_value=SimpleNamespace(id=42))),
        patch.object(telegram_context.aiogram_bot, "get_chat_member", new=AsyncMock(return_value=member)),
    ):
        state = await telegram_context.TelegramContextManager.check_bot_state(session)
    return (
        state.joined is True
        and state.is_admin is True
        and state.can_manage_messages is True
        and state.can_restrict_members is True
        and state.raw["status"] == "administrator"
    )


async def _test_kook_role_and_channel_overrides_are_preserved() -> bool:
    import importlib

    with patch("khl.Bot", return_value=SimpleNamespace()):
        kook_context = importlib.import_module("bots.kook.context")
    from bots.kook.info import target_group_prefix

    class FakeChannel:
        async def fetch_permission(self):
            return SimpleNamespace(
                sync=True,
                roles=[SimpleNamespace(role_id=1, allow=2, deny=4)],
                users=[],
            )

    role = SimpleNamespace(id=1, permissions=1, has_permission=lambda bit: bit == 0)
    guild = SimpleNamespace(
        id="guild",
        master_id="owner",
        fetch_user=AsyncMock(return_value=SimpleNamespace(roles=[1])),
        fetch_roles=AsyncMock(return_value=[role]),
    )
    session = SessionInfo(
        target_id=f"{target_group_prefix}|channel",
        target_from=target_group_prefix,
        client_name="KOOK",
        session_id="bot-state-kook",
    )
    with (
        patch.object(
            kook_context,
            "bot",
            SimpleNamespace(client=SimpleNamespace(fetch_me=AsyncMock(return_value=SimpleNamespace(id="bot")))),
        ),
        patch.object(kook_context, "get_guild", new=AsyncMock(return_value=guild)),
        patch.object(kook_context, "get_channel", new=AsyncMock(return_value=FakeChannel())),
        patch.object(kook_context, "PublicChannel", FakeChannel),
    ):
        state = await kook_context.KOOKContextManager.check_bot_state(session)
    return (
        state.joined is True
        and state.is_admin is True
        and state.can_send_messages is None
        and state.permissions["role_permissions"] == {"1": 1}
        and state.raw["channel_permissions"]["role_overwrites"] == [{"role_id": "1", "allow": 2, "deny": 4}]
    )


@func_case
async def test_bot_state(tester: Tester):
    await tester.test(_test_bot_state_is_serializable_and_preserves_unknown_permissions, "BotState 序列化与未知权限")
    await tester.test(_test_bot_state_rpc_contract_matches_context, "BotState RPC 契约")
    await tester.test(_test_webui_reports_full_state, "WebUI 返回完整机器人权限")
    await tester.test(_test_mock_session_provides_local_bot_state, "测试会话提供本地机器人状态")
    await tester.test(
        _test_discord_permission_state_maps_effective_channel_permissions,
        "Discord 使用频道最终权限映射机器人状态",
    )
    await tester.test(_test_qqbot_group_state_maps_official_bot_state, "QQBot 映射官方群机器人状态")
    await tester.test(_test_non_web_private_context_does_not_claim_management_permissions, "非 Web 私聊不宣称管理权限")
    await tester.test(_test_onebot_group_state_maps_bot_role, "OneBot 映射机器人群角色")
    await tester.test(_test_matrix_power_levels_map_to_common_permissions, "Matrix 映射房间 Power Level")
    await tester.test(_test_telegram_chat_member_status_uses_enum_value, "Telegram 映射 ChatMember 状态")
    await tester.test(_test_kook_role_and_channel_overrides_are_preserved, "KOOK 保留角色与频道权限覆盖")
    return tester
