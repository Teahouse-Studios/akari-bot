"""core.builtins.bot 单元测试 - 主动推送的通道归拢与掉线避让（需要数据库）。"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from core.alive import Alive
from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.session.info import FetchedSessionInfo
from core.database.models import JobQueuePeersTable, JobQueuesTable, TargetUnionInfo, TargetUnionBind
from core.queue.client import post_message, send_private_msg
from core.queue.server import JobQueueServer
from core.queue.contracts import PlatformAPI, ServerAPI
from core.queue.errors import RpcUnavailableError
from core.tester import func_case, Tester


async def _build_channel(prefix: str) -> list[FetchedSessionInfo]:
    union = await TargetUnionInfo.resolve_union(f"{prefix}1|Group|a")
    await union.bind_id(f"{prefix}2|Group|b")
    await TargetUnionBind.filter(union_id=union.union_id).update(channel_id=1)

    sessions = []
    for client in (f"{prefix}1", f"{prefix}2"):
        target_id = f"{client}|Group|{'a' if client.endswith('1') else 'b'}"
        sessions.append(
            await FetchedSessionInfo.assign(
                target_id=target_id, client_name=client, target_from=f"{client}|Group", fetch=True
            )
        )
    return sessions


async def _register_client(client: str) -> None:
    metadata = {
        "target_prefix_list": [f"{client}|Group"],
        "sender_prefix_list": [client],
    }
    lease_until = datetime.now(UTC) + timedelta(seconds=300)
    await JobQueuePeersTable.update_or_create(
        peer_id=f"TEST-PEER-{client}",
        defaults={
            "role": "client",
            "service": client,
            "state": "ready",
            "capabilities": ["rpc", "signals"],
            "metadata": metadata,
            "heartbeat_at": datetime.now(UTC),
            "lease_until": lease_until,
        },
    )
    Alive.refresh_peer(f"TEST-PEER-{client}", client, metadata=metadata, lease_until=lease_until)


async def _take_posted() -> list[tuple[str, list[str]]]:
    rows = await JobQueuesTable.filter(action=PlatformAPI.post_message.name)
    await JobQueuesTable.filter(action=PlatformAPI.post_message.name).delete()
    return [
        (r.args["payload"]["session_info"]["target_id"], r.args["payload"]["session_info"]["next_hops"]) for r in rows
    ]


async def _test_channel_posts_once_with_next_hops():
    alive = Alive.values.copy()
    try:
        sessions = await _build_channel("POSTA")
        Alive.values.clear()
        for client in ("POSTA1", "POSTA2"):
            await _register_client(client)

        await Bot.post_message("", MessageChain.assign("hello"), sessions)
        posted = await _take_posted()

        # 同一条通道对应同一个现实场景，推送两次即发出两条重复消息。
        return posted == [("POSTA1|Group|a", ["POSTA2|Group|b"])]

    except Exception:
        return False
    finally:
        Alive.values.clear()
        Alive.values.update(alive)


async def _test_offline_client_skipped():
    alive = Alive.values.copy()
    try:
        sessions = await _build_channel("POSTB")
        Alive.values.clear()
        # 仅第二个平台在线时，队首应换为该平台，且不再保留下一跳。
        await _register_client("POSTB2")

        await Bot.post_message("", MessageChain.assign("hello"), sessions)
        return await _take_posted() == [("POSTB2|Group|b", [])]

    except Exception:
        return False
    finally:
        Alive.values.clear()
        Alive.values.update(alive)


async def _test_all_offline_posts_nothing():
    alive = Alive.values.copy()
    try:
        sessions = await _build_channel("POSTC")
        Alive.values.clear()

        await Bot.post_message("", MessageChain.assign("hello"), sessions)
        return await _take_posted() == []

    except Exception:
        return False
    finally:
        Alive.values.clear()
        Alive.values.update(alive)


async def _test_rpc_rejects_offline_client():
    alive = Alive.values.copy()
    try:
        Alive.values.clear()
        # 离线目的地须当场抛出错误，不创建无人消费的请求或结果等待者。
        try:
            await JobQueueServer.call("POSTD", PlatformAPI.send_message.name, {})
        except RpcUnavailableError:
            return not await JobQueuesTable.filter(action=PlatformAPI.send_message.name).exists()
        return False

    except Exception:
        return False
    finally:
        Alive.values.clear()
        Alive.values.update(alive)


async def _test_muted_target_posts_nothing():
    alive = Alive.values.copy()
    try:
        sessions = await _build_channel("POSTG")
        Alive.values.clear()
        for client in ("POSTG1", "POSTG2"):
            await _register_client(client)

        union = await TargetUnionInfo.get_by_target_id("POSTG1|Group|a")
        union.muted = True
        await union.save()
        for session in sessions:
            await session.refresh_info()

        await Bot.post_message("", MessageChain.assign("hello"), sessions)
        return await _take_posted() == []

    except Exception:
        return False
    finally:
        Alive.values.clear()
        Alive.values.update(alive)


async def _test_muted_direct_message_skipped():
    union = await TargetUnionInfo.resolve_union("POSTH1|Group|a")
    union.muted = True
    await union.save()
    session = await FetchedSessionInfo.assign(
        target_id="POSTH1|Group|a", client_name="POSTH1", target_from="POSTH1|Group", fetch=True
    )
    submitted = AsyncMock()
    with patch.object(PlatformAPI, "send_message", new=SimpleNamespace(submit=submitted)):
        await Bot.send_direct_message(session, MessageChain.assign("hello"))
    return submitted.await_count == 0


async def _test_post_exception_uses_next_hop():
    session = SimpleNamespace(target_id="POSTE1|Group|a", next_hops=["POSTE2|Group|b"])
    context = SimpleNamespace(send_message=AsyncMock(side_effect=RuntimeError("platform failed")))
    next_hop = AsyncMock()
    message = MessageChain.assign("hello")
    with (
        patch("core.queue.client.resolve_context", new=AsyncMock(return_value=context)),
        patch.object(ServerAPI.post_next_hop, "submit", new=next_hop),
    ):
        result = await post_message(session, message, "wiki")
    next_hop.assert_awaited_once_with(["POSTE2|Group|b"], message, "wiki")
    return result == []


async def _test_private_exception_returns_empty():
    session = SimpleNamespace(target_id="POSTF|Group|a")
    context = SimpleNamespace(send_private_msg=AsyncMock(side_effect=RuntimeError("platform failed")))
    message = MessageChain.assign("hello")
    with patch("core.queue.client.resolve_context", new=AsyncMock(return_value=context)):
        result = await send_private_msg(session, "POSTF|user", message)
    return result == []


@func_case
async def test_post_message(tester: Tester):
    """core.builtins.bot: 主动推送测试"""
    try:
        await tester.test(_test_channel_posts_once_with_next_hops, "同通道只推一次测试")
        await tester.test(_test_offline_client_skipped, "掉线客户端避让测试")
        await tester.test(_test_all_offline_posts_nothing, "全部掉线放弃推送测试")
        await tester.test(_test_muted_target_posts_nothing, "静音场景不接收主动推送测试")
        await tester.test(_test_muted_direct_message_skipped, "静音场景直发消息被拦截测试")
        await tester.test(_test_rpc_rejects_offline_client, "掉线时不入队测试")
        await tester.test(_test_post_exception_uses_next_hop, "平台异常时主动推送继续下一跳测试")
        await tester.test(_test_private_exception_returns_empty, "平台异常时私信返回空消息 ID 测试")
    finally:
        await JobQueuePeersTable.filter(peer_id__startswith="TEST-PEER-POST").delete()

    return tester
