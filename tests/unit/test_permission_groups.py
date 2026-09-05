from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from bots.discord.context import DiscordContextManager
from bots.discord.features import features as discord_features
from bots.kook.features import features as kook_features
from bots.qqbot.context import QQBotContextManager
from bots.qqbot.features import features as qqbot_features, guild_features
from core.builtins.bot import Bot
from core.builtins.session.info import SessionInfo
from core.queue.client import JobQueueClient
from core.queue.contracts import PlatformAPI
from core.tester import Tester, func_case


async def _test_permission_group_features():
    return (
        discord_features.support_permission_group
        and kook_features.support_permission_group
        and guild_features.support_permission_group
        and not qqbot_features.support_permission_group
    )


async def _test_server_queue_forwarding():
    session = await SessionInfo.assign(
        target_id="Discord|Channel|123",
        target_from="Discord|Channel",
        client_name="Discord",
    )
    captured = []

    class Peer:
        @staticmethod
        async def call(target, method, payload, timeout=None):
            captured.append((target, method, payload, True))
            return None

        @staticmethod
        async def submit(target, method, payload, timeout=None):
            captured.append((target, method, payload, False))
            return "task-id"

    grant = await PlatformAPI.grant_permission_group.using(Peer)(
        session, ["Discord|Client|1", "Discord|Client|2"], ["10", "20"], "test"
    )
    revoke = await PlatformAPI.revoke_permission_group.using(Peer).submit(session, "Discord|Client|1", "10")
    grant_args = PlatformAPI.grant_permission_group.decode_arguments(captured[0][2]).arguments
    return (
        grant is None
        and revoke == "task-id"
        and captured[0][0:2] == ("Discord", PlatformAPI.grant_permission_group.name)
        and captured[0][3] is True
        and grant_args["user_id"] == ["Discord|Client|1", "Discord|Client|2"]
        and grant_args["permission_group_id"] == ["10", "20"]
        and grant_args["reason"] == "test"
        and grant_args["session_info"].support_permission_group is False
        and captured[1][0:2] == ("Discord", PlatformAPI.revoke_permission_group.name)
        and captured[1][3] is False
    )


async def _test_client_queue_actions():
    session = await SessionInfo.assign(
        target_id="Discord|Channel|123",
        target_from="Discord|Channel",
        client_name="Discord",
    )
    context = SimpleNamespace(
        grant_permission_group=AsyncMock(return_value=None),
        revoke_permission_group=AsyncMock(return_value=None),
    )
    with (
        patch.object(Bot, "ContextSlots", [context]),
        patch.object(SessionInfo, "refresh_info", new=AsyncMock()),
    ):
        grant = await JobQueueClient.handlers[PlatformAPI.grant_permission_group.name](
            PlatformAPI.grant_permission_group.encode_arguments(session, ["Discord|Client|1"], ["10", "20"], "test")
        )
        revoke = await JobQueueClient.handlers[PlatformAPI.revoke_permission_group.name](
            PlatformAPI.revoke_permission_group.encode_arguments(session, ["Discord|Client|1"], ["10", "20"], "test")
        )

    for method in (context.grant_permission_group, context.revoke_permission_group):
        assert method.await_count == 1
        forwarded, *arguments = method.await_args.args
        assert isinstance(forwarded, SessionInfo)
        assert forwarded.target_id == session.target_id
        assert arguments == [["Discord|Client|1"], ["10", "20"], "test"]
    return grant is None and revoke is None


async def _test_discord_permission_groups():
    role_10 = SimpleNamespace(id=10)
    role_20 = SimpleNamespace(id=20)
    member_1 = SimpleNamespace(add_roles=AsyncMock(), remove_roles=AsyncMock())
    member_2 = SimpleNamespace(add_roles=AsyncMock(), remove_roles=AsyncMock())
    guild = SimpleNamespace(
        id=123,
        get_role=Mock(side_effect=lambda role_id: {10: role_10, 20: role_20}.get(role_id)),
        fetch_roles=AsyncMock(),
        fetch_member=AsyncMock(side_effect=lambda member_id: {1: member_1, 2: member_2}[member_id]),
    )
    session = SessionInfo(
        target_id="Discord|Guild|123",
        target_from="Discord|Guild",
        client_name="Discord",
    )

    with patch("bots.discord.context.get_discord_guild", new=AsyncMock(return_value=guild)):
        await DiscordContextManager.grant_permission_group(
            session,
            ["Discord|Client|1", "Discord|Client|2"],
            ["10", "20"],
            "test",
        )
        await DiscordContextManager.revoke_permission_group(session, "Discord|Client|1", "10")

    member_1.add_roles.assert_awaited_once_with(role_10, role_20, reason="test")
    member_2.add_roles.assert_awaited_once_with(role_10, role_20, reason="test")
    member_1.remove_roles.assert_awaited_once_with(role_10, reason=None)
    return guild.fetch_roles.await_count == 0


async def _test_kook_permission_groups():
    with patch("khl.Bot", return_value=SimpleNamespace()):
        from bots.kook.context import KOOKContextManager

    guild = SimpleNamespace(id="123", grant_role=AsyncMock(), revoke_role=AsyncMock())
    session = SessionInfo(
        target_id="KOOK|Guild|123",
        target_from="KOOK|Guild",
        client_name="KOOK",
    )

    with patch("bots.kook.context.get_guild", new=AsyncMock(return_value=guild)):
        await KOOKContextManager.grant_permission_group(session, ["KOOK|User|1", "KOOK|User|2"], ["10", "20"])
        await KOOKContextManager.revoke_permission_group(session, "KOOK|User|1", "10")

    return (
        guild.grant_role.await_args_list[0].args == ("1", "10")
        and guild.grant_role.await_args_list[-1].args == ("2", "20")
        and guild.grant_role.await_count == 4
        and guild.revoke_role.await_args.args == ("1", "10")
    )


async def _test_qqbot_permission_groups():
    api = SimpleNamespace(
        create_guild_role_member=AsyncMock(),
        delete_guild_role_member=AsyncMock(),
    )
    session = SessionInfo(
        target_id="QQBot|Guild|123|456",
        target_from="QQBot|Guild",
        client_name="QQBot",
    )

    with patch("bots.qqbot.context._get_client", return_value=SimpleNamespace(api=api)):
        await QQBotContextManager.grant_permission_group(session, "QQBot|Tiny|1", ["10", "20"])
        await QQBotContextManager.revoke_permission_group(session, "QQBot|Tiny|1", "10")

    return (
        api.create_guild_role_member.await_args_list[0].args == ("123", "10", "1", "456")
        and api.create_guild_role_member.await_args_list[1].args == ("123", "20", "1", "456")
        and api.delete_guild_role_member.await_args.args == ("123", "10", "1", "456")
    )


@func_case
async def test_permission_groups(tester: Tester):
    """平台原生权限组能力、队列转换与 SDK 调用测试。"""
    await tester.test(_test_permission_group_features, "权限组能力标记测试")
    await tester.test(_test_server_queue_forwarding, "权限组服务器队列转发测试")
    await tester.test(_test_client_queue_actions, "权限组客户端队列动作测试")
    await tester.test(_test_discord_permission_groups, "Discord 权限组授予与移除测试")
    await tester.test(_test_kook_permission_groups, "KOOK 权限组授予与移除测试")
    await tester.test(_test_qqbot_permission_groups, "QQBot 权限组授予与移除测试")
    return tester
