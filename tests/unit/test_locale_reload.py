"""core.queue 单元测试 - 语言文件重载的跨进程广播（需要数据库）。"""

import asyncio

from core.alive import Alive
from core.database.models import JobQueuesTable
from core.queue.base import QueueTaskManager
from core.queue.client import JobQueueClient
from core.queue.server import JobQueueServer
from core.tester import func_case, Tester


async def _answer_reload_jobs(results: dict[str, dict]) -> None:
    """
    扮演客户端取走 reload_locale 任务并回填结果。
    """
    answered = set()
    for _ in range(200):
        for tsk in await JobQueuesTable.filter(action="reload_locale", target_client__in=list(results)):
            task_id = str(tsk.task_id)
            # add_job 先落库、再登记等待，登记完成之前回填会丢失唤醒。
            if task_id in QueueTaskManager.tasks:
                await QueueTaskManager.set_result(task_id, results[tsk.target_client])
                answered.add(tsk.target_client)
        if answered == set(results):
            return
        await asyncio.sleep(0.05)


async def _test_reload_locale_handler_returns_errors():
    """测试语言重载 - 客户端处理器回传错误列表"""
    try:
        handler = JobQueueClient.queue_actions.get("reload_locale")
        if not handler:
            return False
        ret = await handler(None, {})
        return isinstance(ret, dict) and isinstance(ret.get("err"), list)

    except Exception:
        return False


async def _test_reload_locale_without_clients():
    """测试语言重载 - 无客户端在线时不留下无人认领的任务"""
    alive = Alive.values.copy()
    try:
        Alive.values.clear()
        if await JobQueueServer.client_reload_locale_all() != []:
            return False
        return await JobQueuesTable.filter(action="reload_locale").count() == 0

    except Exception:
        return False
    finally:
        Alive.values.clear()
        Alive.values.update(alive)


async def _test_reload_locale_merges_client_errors():
    """测试语言重载 - 广播至各客户端并合并重复的错误"""
    alive = Alive.values.copy()
    timeout = JobQueueServer.RELOAD_LOCALE_TIMEOUT
    try:
        Alive.values.clear()
        JobQueueServer.RELOAD_LOCALE_TIMEOUT = 10
        for client in ("LOCALEA", "LOCALEB"):
            Alive.refresh_alive(client, target_prefix_list=[f"{client}|Group"], sender_prefix_list=[client])

        results = {"LOCALEA": {"err": ["conflict"]}, "LOCALEB": {"err": ["conflict", "broken"]}}
        errs, _ = await asyncio.gather(
            JobQueueServer.client_reload_locale_all(),
            _answer_reload_jobs(results),
        )
        # 各客户端读的是同一批语言文件，重复的错误叠加输出只会淹没真正的差异。
        return sorted(errs) == ["broken", "conflict"]

    except Exception:
        return False
    finally:
        JobQueueServer.RELOAD_LOCALE_TIMEOUT = timeout
        await JobQueuesTable.filter(action="reload_locale").delete()
        Alive.values.clear()
        Alive.values.update(alive)


@func_case
async def test_locale_reload(tester: Tester):
    """core.queue: 语言文件重载广播测试"""
    await tester.test(_test_reload_locale_handler_returns_errors, "客户端重载处理器测试")
    await tester.test(_test_reload_locale_without_clients, "无客户端在线测试")
    await tester.test(_test_reload_locale_merges_client_errors, "多客户端错误合并测试")

    return tester
