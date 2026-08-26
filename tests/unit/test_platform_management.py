"""平台成员管理操作的目标身份单元测试。"""

import importlib
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import ModuleType
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call, patch

import bots.discord.context as discord_context
import bots.discord.bot as discord_bot_module
import bots.onebot.bot as onebot_bot_module
import bots.onebot.context as onebot_context
from bots.kook.features import features as kook_features
from bots.discord.info import sender_prefix, target_channel_prefix, target_dm_channel_prefix
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import Image, Mention, Plain, Audio
from core.builtins.session.info import SessionInfo
from core.tester import Tester, func_case


async def _test_discord_management_uses_requested_user():
    member = SimpleNamespace(timeout=AsyncMock(), kick=AsyncMock(), ban=AsyncMock(), unban=AsyncMock())
    unbanned_user = SimpleNamespace(id=222)
    guild = SimpleNamespace(
        fetch_member=AsyncMock(return_value=member),
        unban=AsyncMock(),
    )
    channel = SimpleNamespace(guild=guild)
    fetch_channel = AsyncMock(return_value=channel)
    fetch_user = AsyncMock(return_value=unbanned_user)
    session = SimpleNamespace(
        target_from=target_channel_prefix,
        target_id=f"{target_channel_prefix}|123",
        sender_from=sender_prefix,
        sender_id=f"{sender_prefix}|111",
    )
    requested_user = f"{sender_prefix}|222"

    with (
        patch.object(discord_context.discord_bot, "fetch_channel", new=fetch_channel),
        patch.object(discord_context.discord_bot, "fetch_user", new=fetch_user),
    ):
        await discord_context.DiscordContextManager.restrict_member(session, requested_user, duration=60, reason="r")
        await discord_context.DiscordContextManager.unrestrict_member(session, requested_user)
        await discord_context.DiscordContextManager.kick_member(session, requested_user, reason="k")
        await discord_context.DiscordContextManager.ban_member(session, requested_user, reason="b")
        await discord_context.DiscordContextManager.unban_member(session, requested_user)

    member_ids = [call.args for call in guild.fetch_member.await_args_list]
    return (
        member_ids == [(222,), (222,), (222,), (222,)]
        and member.timeout.await_count == 2
        and member.kick.await_count == 1
        and member.ban.await_count == 1
        and member.unban.await_count == 0
        and fetch_user.await_args.args == (222,)
        and guild.unban.await_args.args == (unbanned_user,)
    )


async def _test_discord_dm_permission_does_not_require_guild():
    session = SimpleNamespace(
        session_id="discord-dm-permission",
        target_from=target_dm_channel_prefix,
        target_id=f"{target_dm_channel_prefix}|123",
        sender_from=sender_prefix,
        sender_id=f"{sender_prefix}|222",
    )
    fetch_channel = AsyncMock()
    with patch.object(discord_context.discord_bot, "fetch_channel", new=fetch_channel):
        try:
            result = await discord_context.DiscordContextManager.check_native_permission(session)
        except Exception:
            return False
    return result is True and fetch_channel.await_count == 0


async def _test_discord_send_failure_returns_empty():
    session = SessionInfo(
        target_id=f"{target_channel_prefix}|123",
        target_from=target_channel_prefix,
        sender_id=f"{sender_prefix}|222",
        sender_from=sender_prefix,
        client_name="Discord",
        session_id="discord-send-failure",
    )
    channel = SimpleNamespace()
    with (
        patch.object(discord_context.discord_bot, "fetch_channel", new=AsyncMock(return_value=channel)),
        patch.object(
            discord_context,
            "execute_discord_payloads",
            new=AsyncMock(side_effect=RuntimeError("send failed")),
        ),
    ):
        try:
            result = await discord_context.DiscordContextManager.send_message(
                session,
                MessageChain.assign("hello"),
                quote=False,
            )
        except Exception:
            return False
    return result == []


async def _test_discord_message_without_reply_keeps_none():
    assigned = SimpleNamespace()
    assign = AsyncMock(return_value=assigned)
    process = AsyncMock()
    fake_bot = SimpleNamespace(user=SimpleNamespace(id=999))
    message = SimpleNamespace(
        author=SimpleNamespace(id=222, name="member", bot=False),
        channel=SimpleNamespace(id=123),
        reference=None,
        content="~ping",
        id=456,
    )
    with (
        patch.object(discord_bot_module, "discord_bot", new=fake_bot),
        patch.object(discord_bot_module, "ensure_client_initialized", new=AsyncMock()),
        patch.object(discord_bot_module, "to_message_chain", new=AsyncMock(return_value=MessageChain.assign("~ping"))),
        patch.object(discord_bot_module.SessionInfo, "assign", new=assign),
        patch.object(discord_bot_module.Bot, "process_message", new=process),
        patch.object(discord_bot_module, "mention_required", False),
    ):
        await discord_bot_module.on_message(message)
    return assign.await_args.kwargs["reply_id"] is None and process.await_args.args == (assigned, message)


async def _test_discord_raw_reaction_builds_usable_context():
    assigned = SimpleNamespace()
    assign = AsyncMock(return_value=assigned)
    process = AsyncMock()
    origin = SimpleNamespace(id=456)
    channel = SimpleNamespace(id=123, fetch_message=AsyncMock(return_value=origin))
    member = SimpleNamespace(id=222)
    payload = SimpleNamespace(
        user_id=222,
        channel_id=123,
        message_id=456,
        member=member,
        emoji=SimpleNamespace(name="✅"),
    )
    fake_bot = SimpleNamespace(
        user=SimpleNamespace(id=999),
        fetch_channel=AsyncMock(return_value=channel),
        fetch_user=AsyncMock(),
    )
    with (
        patch.object(discord_bot_module, "discord_bot", new=fake_bot),
        patch.object(discord_bot_module, "ensure_client_initialized", new=AsyncMock()),
        patch.object(discord_bot_module.SessionInfo, "assign", new=assign),
        patch.object(discord_bot_module.Bot, "process_message", new=process),
    ):
        await discord_bot_module.on_raw_reaction_add(payload)

    context = process.await_args.args[1]
    return (
        process.await_args.args[0] is assigned
        and context.channel is channel
        and context.user is member
        and context.message is origin
        and assign.await_args.kwargs.get("message_id") is None
        and assign.await_args.kwargs["reply_id"] == "456"
        and channel.fetch_message.await_args.args == (456,)
    )


async def _test_discord_raw_reaction_without_member_fetches_user():
    assigned = SimpleNamespace()
    assign = AsyncMock(return_value=assigned)
    process = AsyncMock()
    origin = SimpleNamespace(id=456)
    channel = SimpleNamespace(id=123, fetch_message=AsyncMock(return_value=origin))
    user = SimpleNamespace(id=222)
    payload = SimpleNamespace(
        user_id=222,
        channel_id=123,
        message_id=456,
        member=None,
        emoji=SimpleNamespace(name="✅"),
    )
    fake_bot = SimpleNamespace(
        user=SimpleNamespace(id=999),
        fetch_channel=AsyncMock(return_value=channel),
        fetch_user=AsyncMock(return_value=user),
    )
    with (
        patch.object(discord_bot_module, "discord_bot", new=fake_bot),
        patch.object(discord_bot_module, "ensure_client_initialized", new=AsyncMock()),
        patch.object(discord_bot_module.SessionInfo, "assign", new=assign),
        patch.object(discord_bot_module.Bot, "process_message", new=process),
    ):
        await discord_bot_module.on_raw_reaction_add(payload)

    context = process.await_args.args[1]
    return context.user is user and fake_bot.fetch_user.await_args.args == (222,)


async def _test_discord_reaction_context_preserves_operation_semantics():
    origin = SimpleNamespace(
        id=456,
        add_reaction=AsyncMock(),
        remove_reaction=AsyncMock(),
        delete=AsyncMock(),
    )
    member = SimpleNamespace(id=222)
    bot_user = SimpleNamespace(id=999)
    channel = SimpleNamespace(id=123)
    reaction_ctx = discord_context.DiscordReactionContext(
        channel=channel,
        user=member,
        message=origin,
        emoji="✅",
    )
    session = SessionInfo(
        target_id=f"{target_channel_prefix}|123",
        target_from=target_channel_prefix,
        sender_id=f"{sender_prefix}|222",
        sender_from=sender_prefix,
        client_name="Discord",
        session_id="discord-reaction-contract",
        message_id=None,
        reply_id="456",
        locale=SimpleNamespace(t=lambda key: key),
    )
    execute = AsyncMock(return_value=[])
    fake_bot = SimpleNamespace(user=bot_user, fetch_channel=AsyncMock(return_value=channel))
    with (
        patch.object(discord_context.DiscordContextManager, "context", new={session.session_id: reaction_ctx}),
        patch.object(discord_context, "discord_bot", new=fake_bot),
        patch.object(discord_context, "build_discord_payloads", new=AsyncMock(return_value=[])),
        patch.object(discord_context, "build_discord_button_view", new=Mock(return_value=None)),
        patch.object(discord_context, "execute_discord_payloads", new=execute),
    ):
        await discord_context.DiscordContextManager.send_message(session, MessageChain.assign("reply"), quote=True)
        await discord_context.DiscordContextManager.delete_message(session, session.message_id)
        await discord_context.DiscordContextManager.add_reaction(session, session.message_id, "🔥")
        await discord_context.DiscordContextManager.remove_reaction(session, session.message_id, "🔥")

    return (
        execute.await_args.kwargs["reference"] is origin
        and origin.add_reaction.await_args_list == [call("🔥")]
        and origin.remove_reaction.await_args_list == [call("✅", member), call("🔥", bot_user)]
        and origin.delete.await_count == 0
    )


async def _test_discord_reaction_user_permission_fetches_member():
    fetched_member = SimpleNamespace(id=222)
    guild = SimpleNamespace(fetch_member=AsyncMock(return_value=fetched_member))
    channel = SimpleNamespace(
        id=123,
        guild=guild,
        permissions_for=Mock(return_value=SimpleNamespace(administrator=True)),
    )
    reaction_ctx = discord_context.DiscordReactionContext(
        channel=channel,
        user=SimpleNamespace(id=222),
        message=SimpleNamespace(id=456),
        emoji="✅",
    )
    session = SessionInfo(
        target_id=f"{target_channel_prefix}|123",
        target_from=target_channel_prefix,
        sender_id=f"{sender_prefix}|222",
        sender_from=sender_prefix,
        client_name="Discord",
        session_id="discord-reaction-permission",
    )
    with patch.object(
        discord_context.DiscordContextManager,
        "context",
        new={session.session_id: reaction_ctx},
    ):
        result = await discord_context.DiscordContextManager.check_native_permission(session)
    return (
        result is True
        and guild.fetch_member.await_args.args == (222,)
        and channel.permissions_for.call_args.args == (fetched_member,)
    )


async def _test_onebot_missing_optional_ids_keep_none():
    assigned = SimpleNamespace()
    assign = AsyncMock(return_value=assigned)
    process = AsyncMock()
    event = SimpleNamespace(
        message="~ping",
        detail_type="group",
        group_id=123,
        user_id=222,
        self_id=999,
        message_id=456,
        sender={"nickname": "member"},
    )
    with (
        patch.object(onebot_bot_module, "qq_account", None),
        patch.object(onebot_bot_module, "mention_required", False),
        patch.object(onebot_bot_module, "to_message_chain", new=AsyncMock(return_value=MessageChain.assign("~ping"))),
        patch.object(onebot_bot_module.SessionInfo, "assign", new=assign),
        patch.object(onebot_bot_module.Bot, "process_message", new=process),
    ):
        await onebot_bot_module.message_handler(event)
    return (
        assign.await_args.kwargs["reply_id"] is None
        and assign.await_args.kwargs["bot_id"] is None
        and process.await_args.args == (assigned, event)
    )


async def _test_onebot_private_list_failure_returns_empty():
    session = SessionInfo(
        target_id="QQ|Group|123",
        target_from="QQ|Group",
        sender_id="QQ|123",
        sender_from="QQ",
        client_name="QQ",
        session_id="onebot-private-list-failure",
    )
    send = AsyncMock()
    with (
        patch.object(
            onebot_context,
            "get_available_private_list",
            new=AsyncMock(side_effect=RuntimeError("friend list failed")),
        ),
        patch.object(onebot_context.OneBotContextManager, "send_message", new=send),
    ):
        try:
            result = await onebot_context.OneBotContextManager.send_private_msg(
                session,
                "QQ|456",
                MessageChain.assign("hello"),
            )
        except Exception:
            return False
    return result == [] and send.await_count == 0


def _test_kook_does_not_advertise_unimplemented_typing():
    return not kook_features.support_typing


async def _test_kook_call_api_rejects_business_error():
    fake_client = ModuleType("bots.kook.client")
    fake_client.bot = SimpleNamespace()
    fake_client.token = "test"
    previous_client = sys.modules.get("bots.kook.client")
    previous_context = sys.modules.pop("bots.kook.context", None)
    sys.modules["bots.kook.client"] = fake_client

    class FakeHTTPClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def post(self, *args, **kwargs):
            return SimpleNamespace(status_code=200, text='{"code": 40000, "message": "denied"}')

    try:
        kook_context = importlib.import_module("bots.kook.context")
        with patch.object(kook_context.httpx, "AsyncClient", new=FakeHTTPClient):
            try:
                await kook_context.call_api("message/delete", msg_id="1")
            except ValueError as exc:
                return exc.args == ({"code": 40000, "message": "denied"},)
        return False
    finally:
        sys.modules.pop("bots.kook.context", None)
        if previous_context is not None:
            sys.modules["bots.kook.context"] = previous_context
        if previous_client is None:
            sys.modules.pop("bots.kook.client", None)
        else:
            sys.modules["bots.kook.client"] = previous_client


async def _test_kook_missing_channel_returns_empty():
    fake_client = ModuleType("bots.kook.client")
    fake_client.bot = SimpleNamespace(client=SimpleNamespace(fetch_public_channel=AsyncMock(return_value=None)))
    fake_client.token = "test"
    previous_client = sys.modules.get("bots.kook.client")
    previous_context = sys.modules.pop("bots.kook.context", None)
    sys.modules["bots.kook.client"] = fake_client
    try:
        kook_context = importlib.import_module("bots.kook.context")
        session = SessionInfo(
            target_id="KOOK|Group|missing",
            target_from="KOOK|Group",
            sender_id="KOOK|Client|1",
            sender_from="KOOK|Client",
            client_name="KOOK",
            session_id="kook-missing-channel",
        )
        try:
            result = await kook_context.KOOKContextManager.send_message(session, MessageChain.assign("hello"))
        except Exception:
            return False
        return result == []
    finally:
        sys.modules.pop("bots.kook.context", None)
        if previous_context is not None:
            sys.modules["bots.kook.context"] = previous_context
        if previous_client is None:
            sys.modules.pop("bots.kook.client", None)
        else:
            sys.modules["bots.kook.client"] = previous_client


async def _test_kook_media_upload_closes_files():
    opened_files = []

    async def create_asset(file):
        opened_files.append(file)
        return "https://asset"

    channel = SimpleNamespace(send=AsyncMock(side_effect=[{"msg_id": "image"}, {"msg_id": "audio"}]))
    fake_client = ModuleType("bots.kook.client")
    fake_client.bot = SimpleNamespace(
        client=SimpleNamespace(fetch_public_channel=AsyncMock(return_value=channel)),
        create_asset=create_asset,
    )
    fake_client.token = "test"
    previous_client = sys.modules.get("bots.kook.client")
    previous_context = sys.modules.pop("bots.kook.context", None)
    sys.modules["bots.kook.client"] = fake_client
    try:
        kook_context = importlib.import_module("bots.kook.context")
        with TemporaryDirectory() as directory:
            image_path = Path(directory) / "image.png"
            audio_path = Path(directory) / "audio.ogg"
            image_path.write_bytes(b"image")
            audio_path.write_bytes(b"audio")
            session = SessionInfo(
                target_id="KOOK|Group|1",
                target_from="KOOK|Group",
                sender_id="KOOK|Client|1",
                sender_from="KOOK|Client",
                client_name="KOOK",
                session_id="kook-media-close",
                support_image=True,
                support_audio=True,
            )
            result = await kook_context.KOOKContextManager.send_message(
                session,
                MessageChain.assign([Image(image_path), Audio(audio_path)]),
                quote=False,
            )
            files_closed = len(opened_files) == 2 and all(file.closed for file in opened_files)
            # 修复前 Windows 不允许 TemporaryDirectory 删除仍被占用的媒体文件；
            # 测试完成断言取样后主动关闭，避免清理异常掩盖实际失败结果。
            for file in opened_files:
                if not file.closed:
                    file.close()
        return result == ["image", "audio"] and files_closed
    finally:
        for file in opened_files:
            if not file.closed:
                file.close()
        sys.modules.pop("bots.kook.context", None)
        if previous_context is not None:
            sys.modules["bots.kook.context"] = previous_context
        if previous_client is None:
            sys.modules.pop("bots.kook.client", None)
        else:
            sys.modules["bots.kook.client"] = previous_client


async def _test_kook_send_failure_returns_empty():
    channel = SimpleNamespace(send=AsyncMock(side_effect=RuntimeError("send failed")))
    fake_client = ModuleType("bots.kook.client")
    fake_client.bot = SimpleNamespace(client=SimpleNamespace(fetch_public_channel=AsyncMock(return_value=channel)))
    fake_client.token = "test"
    previous_client = sys.modules.get("bots.kook.client")
    previous_context = sys.modules.pop("bots.kook.context", None)
    sys.modules["bots.kook.client"] = fake_client
    try:
        kook_context = importlib.import_module("bots.kook.context")
        session = SessionInfo(
            target_id="KOOK|Group|1",
            target_from="KOOK|Group",
            sender_id="KOOK|Client|1",
            sender_from="KOOK|Client",
            client_name="KOOK",
            session_id="kook-send-failure",
        )
        try:
            result = await kook_context.KOOKContextManager.send_message(
                session,
                MessageChain.assign("hello"),
                quote=False,
            )
        except Exception:
            return False
        return result == []
    finally:
        sys.modules.pop("bots.kook.context", None)
        if previous_context is not None:
            sys.modules["bots.kook.context"] = previous_context
        if previous_client is None:
            sys.modules.pop("bots.kook.client", None)
        else:
            sys.modules["bots.kook.client"] = previous_client


async def _test_kook_reaction_event_uses_fetched_channel():
    channel = SimpleNamespace(send=AsyncMock(return_value={"msg_id": "sent"}))
    fake_client = ModuleType("bots.kook.client")
    fake_client.bot = SimpleNamespace(client=SimpleNamespace(fetch_public_channel=AsyncMock(return_value=channel)))
    fake_client.token = "test"
    previous_client = sys.modules.get("bots.kook.client")
    previous_context = sys.modules.pop("bots.kook.context", None)
    sys.modules["bots.kook.client"] = fake_client
    try:
        kook_context = importlib.import_module("bots.kook.context")
        session = SessionInfo(
            target_id="KOOK|Group|1",
            target_from="KOOK|Group",
            sender_id="KOOK|Client|1",
            sender_from="KOOK|Client",
            client_name="KOOK",
            session_id="kook-reaction-context",
            message_id="reaction-event-id",
            reply_id="origin-message-id",
        )
        reaction_ctx = kook_context.KOOKReactionContext(
            origin_message_id="origin-message-id",
            emoji="✅",
            user_id="42",
        )
        api = AsyncMock()
        with (
            patch.object(kook_context.KOOKContextManager, "context", new={session.session_id: reaction_ctx}),
            patch.object(kook_context, "get_channel", new=AsyncMock(return_value=channel)),
            patch.object(kook_context, "call_api", new=api),
        ):
            result = await kook_context.KOOKContextManager.send_message(
                session,
                MessageChain.assign("hello"),
                quote=True,
            )
            await kook_context.KOOKContextManager.delete_message(session, session.message_id)
            await kook_context.KOOKContextManager.add_reaction(session, session.message_id, "🔥")
            await kook_context.KOOKContextManager.remove_reaction(session, session.message_id, "🔥")
        return (
            result == ["sent"]
            and channel.send.await_args == call("hello", quote="origin-message-id")
            and api.await_args_list
            == [
                call(
                    "message/delete-reaction",
                    msg_id="origin-message-id",
                    emoji="✅",
                    user_id="42",
                ),
                call("message/add-reaction", msg_id="origin-message-id", emoji="🔥"),
                call("message/delete-reaction", msg_id="origin-message-id", emoji="🔥"),
            ]
        )
    finally:
        sys.modules.pop("bots.kook.context", None)
        if previous_context is not None:
            sys.modules["bots.kook.context"] = previous_context
        if previous_client is None:
            sys.modules.pop("bots.kook.client", None)
        else:
            sys.modules["bots.kook.client"] = previous_client


async def _test_kook_reaction_entry_preserves_event_and_origin_ids():
    assigned = SimpleNamespace()
    assign = AsyncMock(return_value=assigned)
    process = AsyncMock()
    event = SimpleNamespace(
        id="reaction-event-id",
        extra={
            "body": {
                "user_id": "42",
                "channel_id": "channel-id",
                "msg_id": "origin-message-id",
                "emoji": {"id": "✅"},
            }
        },
    )
    event_bot = SimpleNamespace(client=SimpleNamespace(me=SimpleNamespace(id="bot-id")))

    def register_handler(*args, **kwargs):
        return lambda func: func

    adapter_bot = SimpleNamespace(
        me=SimpleNamespace(id="bot-id"),
        client=SimpleNamespace(me=SimpleNamespace(id="bot-id")),
        on_message=register_handler,
        on_event=register_handler,
        on_startup=register_handler,
    )
    fake_client = ModuleType("bots.kook.client")
    fake_client.bot = adapter_bot
    fake_client.token = "test"
    previous_client = sys.modules.get("bots.kook.client")
    previous_context = sys.modules.pop("bots.kook.context", None)
    previous_bot_module = sys.modules.pop("bots.kook.bot", None)
    sys.modules["bots.kook.client"] = fake_client
    try:
        kook_bot_module = importlib.import_module("bots.kook.bot")
        with (
            patch.object(kook_bot_module, "ignored_sender", new=[]),
            patch.object(kook_bot_module.SessionInfo, "assign", new=assign),
            patch.object(kook_bot_module.Bot, "process_message", new=process),
        ):
            await kook_bot_module.add_reaction(event_bot, event)
            await kook_bot_module.add_reaction(
                event_bot,
                SimpleNamespace(
                    id="invalid-reaction-event-id",
                    extra={"body": {"user_id": "42", "channel_id": "channel-id", "emoji": {"id": "✅"}}},
                ),
            )

        context = process.await_args.args[1]
        return (
            process.await_args.args[0] is assigned
            and assign.await_count == 1
            and process.await_count == 1
            and assign.await_args.kwargs["message_id"] == "reaction-event-id"
            and assign.await_args.kwargs["reply_id"] == "origin-message-id"
            and context.origin_message_id == "origin-message-id"
            and context.emoji == "✅"
            and context.user_id == "42"
        )
    finally:
        sys.modules.pop("bots.kook.bot", None)
        sys.modules.pop("bots.kook.context", None)
        if previous_bot_module is not None:
            sys.modules["bots.kook.bot"] = previous_bot_module
        if previous_context is not None:
            sys.modules["bots.kook.context"] = previous_context
        if previous_client is None:
            sys.modules.pop("bots.kook.client", None)
        else:
            sys.modules["bots.kook.client"] = previous_client


async def _test_kook_private_reaction_uses_direct_message_api():
    channel = SimpleNamespace(send=AsyncMock(return_value={"msg_id": "sent"}))
    fake_client = ModuleType("bots.kook.client")
    fake_client.bot = SimpleNamespace(client=SimpleNamespace(fetch_user=AsyncMock(return_value=channel)))
    fake_client.token = "test"
    previous_client = sys.modules.get("bots.kook.client")
    previous_context = sys.modules.pop("bots.kook.context", None)
    sys.modules["bots.kook.client"] = fake_client
    try:
        kook_context = importlib.import_module("bots.kook.context")
        session = SessionInfo(
            target_id="KOOK|Person|42",
            target_from="KOOK|Person",
            sender_id="KOOK|Client|42",
            sender_from="KOOK|Client",
            client_name="KOOK",
            session_id="kook-private-reaction",
            message_id="private-reaction-event-id",
            reply_id="private-origin-message-id",
            is_private=True,
        )
        reaction_ctx = kook_context.KOOKReactionContext(
            origin_message_id="private-origin-message-id",
            emoji="✅",
            user_id="42",
        )
        api = AsyncMock()
        with (
            patch.object(kook_context.KOOKContextManager, "context", new={session.session_id: reaction_ctx}),
            patch.object(kook_context, "get_channel", new=AsyncMock(return_value=channel)),
            patch.object(kook_context, "call_api", new=api),
        ):
            result = await kook_context.KOOKContextManager.send_message(
                session,
                MessageChain.assign("hello"),
                quote=True,
            )
            await kook_context.KOOKContextManager.delete_message(session, session.message_id)
            await kook_context.KOOKContextManager.add_reaction(session, session.message_id, "🔥")
            await kook_context.KOOKContextManager.remove_reaction(session, session.message_id, "🔥")
        return (
            result == ["sent"]
            and channel.send.await_args == call("hello", quote="private-origin-message-id")
            and api.await_args_list
            == [
                call(
                    "direct-message/delete-reaction",
                    msg_id="private-origin-message-id",
                    emoji="✅",
                    user_id="42",
                ),
                call("direct-message/add-reaction", msg_id="private-origin-message-id", emoji="🔥"),
                call("direct-message/delete-reaction", msg_id="private-origin-message-id", emoji="🔥"),
            ]
        )
    finally:
        sys.modules.pop("bots.kook.context", None)
        if previous_context is not None:
            sys.modules["bots.kook.context"] = previous_context
        if previous_client is None:
            sys.modules.pop("bots.kook.client", None)
        else:
            sys.modules["bots.kook.client"] = previous_client


async def _test_kook_preserves_ids_before_send_failure():
    channel = SimpleNamespace(send=AsyncMock(side_effect=[{"msg_id": "first"}, RuntimeError("send failed")]))
    fake_client = ModuleType("bots.kook.client")
    fake_client.bot = SimpleNamespace(client=SimpleNamespace(fetch_public_channel=AsyncMock(return_value=channel)))
    fake_client.token = "test"
    previous_client = sys.modules.get("bots.kook.client")
    previous_context = sys.modules.pop("bots.kook.context", None)
    sys.modules["bots.kook.client"] = fake_client
    try:
        kook_context = importlib.import_module("bots.kook.context")
        session = SessionInfo(
            target_id="KOOK|Group|1",
            target_from="KOOK|Group",
            sender_id="KOOK|Client|1",
            sender_from="KOOK|Client",
            client_name="KOOK",
            session_id="kook-partial-send",
            support_mention=True,
        )
        result = await kook_context.KOOKContextManager.send_message(
            session,
            MessageChain.assign([Plain("hello"), Mention("KOOK|2")]),
            quote=False,
        )
        return result == ["first"] and channel.send.await_count == 2
    finally:
        sys.modules.pop("bots.kook.context", None)
        if previous_context is not None:
            sys.modules["bots.kook.context"] = previous_context
        if previous_client is None:
            sys.modules.pop("bots.kook.client", None)
        else:
            sys.modules["bots.kook.client"] = previous_client


@func_case
async def test_platform_management(tester: Tester):
    """平台管理操作必须作用于显式指定的成员。"""
    await tester.test(_test_discord_management_uses_requested_user, "Discord 成员管理使用目标用户")
    await tester.test(_test_discord_dm_permission_does_not_require_guild, "Discord 私聊权限不访问服务器 API")
    await tester.test(_test_discord_send_failure_returns_empty, "Discord 发送异常返回空消息 ID")
    await tester.test(_test_discord_message_without_reply_keeps_none, "Discord 无引用消息保留空 reply_id")
    await tester.test(_test_discord_raw_reaction_builds_usable_context, "Discord Reaction 恢复可用上下文")
    await tester.test(
        _test_discord_raw_reaction_without_member_fetches_user,
        "Discord Reaction 成员缺失时补取用户",
    )
    await tester.test(
        _test_discord_reaction_context_preserves_operation_semantics,
        "Discord Reaction 区分删除用户 Reaction 与移除机器人 Reaction",
    )
    await tester.test(
        _test_discord_reaction_user_permission_fetches_member,
        "Discord Reaction 权限检查补取成员",
    )
    await tester.test(_test_onebot_missing_optional_ids_keep_none, "OneBot 缺失引用和机器人 ID 时保留空值")
    await tester.test(_test_onebot_private_list_failure_returns_empty, "OneBot 好友列表查询失败返回空消息 ID")
    await tester.test(_test_kook_does_not_advertise_unimplemented_typing, "KOOK 不声明未实现的 typing")
    await tester.test(_test_kook_call_api_rejects_business_error, "KOOK API 拒绝业务错误响应")
    await tester.test(_test_kook_missing_channel_returns_empty, "KOOK 目标不存在时返回发送失败")
    await tester.test(_test_kook_media_upload_closes_files, "KOOK 媒体上传关闭文件句柄")
    await tester.test(_test_kook_send_failure_returns_empty, "KOOK 发送异常返回空消息 ID")
    await tester.test(
        _test_kook_reaction_event_uses_fetched_channel,
        "KOOK Reaction 区分事件、原消息与用户 Reaction",
    )
    await tester.test(
        _test_kook_reaction_entry_preserves_event_and_origin_ids,
        "KOOK Reaction 入口保留事件与原消息 ID",
    )
    await tester.test(
        _test_kook_private_reaction_uses_direct_message_api,
        "KOOK 私聊 Reaction 使用私信 API",
    )
    await tester.test(_test_kook_preserves_ids_before_send_failure, "KOOK 后续失败保留已发送 ID")
    return tester
