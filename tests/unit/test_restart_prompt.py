"""core.server.init 单元测试 - 重启提示的送达（需要数据库）。

server 进程重启后 `Alive` 保活表随进程内存一并清空，须等目标客户端重新上报保活
才能投递重启提示，否则 `JobQueueServer.add_job` 会以「客户端掉线」为由将其丢弃。
"""

import asyncio

import orjson

from core.alive import Alive
from core.builtins.converter import converter
from core.builtins.session.info import SessionInfo
from core.constants import PrivateAssets
from core.database.models import JobQueuesTable
from core.server.init import load_prompt
from core.tester import func_case, Tester


async def _write_restart_cache(client: str) -> None:
    """写入重启缓存，等同于 `modules.core.su_utils.write_restart_cache`。"""
    session_info = await SessionInfo.assign(
        target_id=f"{client}|Group|1",
        target_from=f"{client}|Group",
        client_name=client,
        sender_id=f"{client}|1",
        create=True,
    )
    author_cache = PrivateAssets.path / ".cache_restart_author"
    author_cache.write_bytes(orjson.dumps(converter.unstructure(session_info)))
    # load_prompt 会一并读取模块加载结果，该文件由 load_modules 写出，此处补齐以隔离依赖
    loader_cache = PrivateAssets.path / ".cache_loader"
    if not loader_cache.exists():
        loader_cache.write_text("")


async def _prompt_sent() -> bool:
    """重启提示是否已入队。"""
    return await JobQueuesTable.filter(action="send_message").exists()


async def _reset(client: str) -> None:
    Alive.values.clear()
    await JobQueuesTable.filter(action="send_message").delete()
    await _write_restart_cache(client)


def _cleanup(alive: dict) -> None:
    (PrivateAssets.path / ".cache_restart_author").unlink(missing_ok=True)
    Alive.values.clear()
    Alive.values.update(alive)


async def _test_waits_for_client_to_come_online():
    """测试重启提示 - 客户端在提示发出前尚未上报保活时，应等其上线后再投递

    server 与各 bot 子进程一同重启，`load_prompt` 执行时保活表必然为空：
    保活信号须经 `check_job_queue` 轮询取回才会落到 `Alive`，而该轮询启动于
    `load_prompt` 之后。若不等待即发送，提示会被 `add_job` 的掉线检查静默丢弃。
    """
    client = "RESTARTA"
    alive = Alive.values.copy()
    try:
        await _reset(client)

        async def _come_online():
            await asyncio.sleep(0.5)
            Alive.refresh_alive(client, target_prefix_list=[f"{client}|Group"], sender_prefix_list=[client])

        task = asyncio.create_task(_come_online())
        await load_prompt(None, timeout=10)
        await task
        return await _prompt_sent()

    except Exception:
        return False
    finally:
        _cleanup(alive)


async def _test_gives_up_when_client_never_online():
    """测试重启提示 - 客户端始终不上线时，应在超时后放弃而非一直等待

    重启提示并非关键路径，客户端确已掉线时无限等待只会让 server 卡在初始化阶段。
    """
    client = "RESTARTB"
    alive = Alive.values.copy()
    try:
        await _reset(client)

        await asyncio.wait_for(load_prompt(None, timeout=1), timeout=10)
        # 超时放弃后不应残留缓存，否则下次启动会重复投递
        return not await _prompt_sent() and not (PrivateAssets.path / ".cache_restart_author").exists()

    except (Exception, asyncio.TimeoutError):
        return False
    finally:
        _cleanup(alive)


@func_case
async def test_restart_prompt(tester: Tester):
    """core.server.init: 重启提示送达测试"""
    await tester.test(_test_waits_for_client_to_come_online, "等待客户端上线后投递测试")
    await tester.test(_test_gives_up_when_client_never_online, "客户端不上线时超时放弃测试")

    return tester
