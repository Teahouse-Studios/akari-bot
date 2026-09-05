"""core.builtins.bot 单元测试 - 主动推送的通道归拢与掉线避让（需要数据库）。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from core.alive import Alive
from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.session.info import FetchedSessionInfo
from core.database.models import JobQueuesTable, TargetUnionInfo, TargetUnionBind
from core.queue.client import post_message, send_private_msg
from core.queue.server import JobQueueServer
from core.queue.contracts import PlatformAPI, ServerAPI
from core.queue.errors import RpcUnavailableError
from core.tester import func_case, Tester


async def _build_channel(prefix: str) -> list[FetchedSessionInfo]:
    """
    构造一组「同一条消息通道、分属两个平台」的会话。
    """
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


async def _take_posted() -> list[tuple[str, list[str]]]:
    """
    取出并清空已入队的主动推送任务，返回 ``(目标会话, 下一跳列表)``。
    """
    rows = await JobQueuesTable.filter(action=PlatformAPI.post_message.name)
    await JobQueuesTable.filter(action=PlatformAPI.post_message.name).delete()
    return [
        (r.args["payload"]["session_info"]["target_id"], r.args["payload"]["session_info"]["next_hops"]) for r in rows
    ]


async def _test_channel_posts_once_with_next_hops():
    """测试主动推送 - 同通道只推队首，其余会话作为下一跳"""
    alive = Alive.values.copy()
    try:
        sessions = await _build_channel("POSTA")
        Alive.values.clear()
        for client in ("POSTA1", "POSTA2"):
            Alive.refresh_alive(client, target_prefix_list=[f"{client}|Group"], sender_prefix_list=[client])

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
    """测试主动推送 - 掉线的客户端不做队首，改由在线的顶上"""
    alive = Alive.values.copy()
    try:
        sessions = await _build_channel("POSTB")
        Alive.values.clear()
        # 仅第二个平台在线时，队首应换为该平台，且不再保留下一跳。
        Alive.refresh_alive("POSTB2", target_prefix_list=["POSTB2|Group"], sender_prefix_list=["POSTB2"])

        await Bot.post_message("", MessageChain.assign("hello"), sessions)
        return await _take_posted() == [("POSTB2|Group|b", [])]

    except Exception:
        return False
    finally:
        Alive.values.clear()
        Alive.values.update(alive)


async def _test_all_offline_posts_nothing():
    """测试主动推送 - 通道内全部掉线时直接放弃，不留下无人认领的任务"""
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
    """测试队列 - 目标客户端掉线时当场失败，而不是永久等下去"""
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
    await tester.test(_test_channel_posts_once_with_next_hops, "同通道只推一次测试")
    await tester.test(_test_offline_client_skipped, "掉线客户端避让测试")
    await tester.test(_test_all_offline_posts_nothing, "全部掉线放弃推送测试")
    await tester.test(_test_rpc_rejects_offline_client, "掉线时不入队测试")
    await tester.test(_test_post_exception_uses_next_hop, "平台异常时主动推送继续下一跳测试")
    await tester.test(_test_private_exception_returns_empty, "平台异常时私信返回空消息 ID 测试")

    return tester
