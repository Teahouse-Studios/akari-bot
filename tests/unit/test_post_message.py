"""core.builtins.bot 单元测试 - 主动推送的通道归拢与掉线避让（需要数据库）。"""

from core.alive import Alive
from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.session.info import FetchedSessionInfo
from core.database.models import JobQueuesTable, TargetUnionInfo, TargetUnionBind
from core.queue.server import JobQueueServer
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
    rows = await JobQueuesTable.filter(action="post_message")
    await JobQueuesTable.filter(action="post_message").delete()
    return [(r.args["session_info"]["target_id"], r.args["session_info"]["next_hops"]) for r in rows]


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


async def _test_add_job_gives_up_on_offline_client():
    """测试队列 - 目标客户端掉线时当场失败，而不是永久等下去"""
    alive = Alive.values.copy()
    try:
        Alive.values.clear()
        # wait=True 所等待的 Event 不会再被置位，若不提前拦截将使整条发送路径永久阻塞。
        got = await JobQueueServer.add_job("POSTD", "send_message", {}, wait=True)
        if got != {}:
            return False
        return await JobQueuesTable.filter(action="send_message").count() == 0

    except Exception:
        return False
    finally:
        Alive.values.clear()
        Alive.values.update(alive)


@func_case
async def test_post_message(tester: Tester):
    """core.builtins.bot: 主动推送测试"""
    await tester.test(_test_channel_posts_once_with_next_hops, "同通道只推一次测试")
    await tester.test(_test_offline_client_skipped, "掉线客户端避让测试")
    await tester.test(_test_all_offline_posts_nothing, "全部掉线放弃推送测试")
    await tester.test(_test_add_job_gives_up_on_offline_client, "掉线时不入队测试")

    return tester
