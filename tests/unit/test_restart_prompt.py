"""core.server.init 单元测试 - 重启提示的送达（需要数据库）。"""

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import orjson

from core.alive import Alive
from core.builtins.converter import converter
from core.builtins.session.info import SessionInfo
from core.constants import PrivateData
from core.database.models import JobQueuePeersTable, JobQueuesTable
from core.server.init import load_prompt
from core.queue.contracts import PlatformAPI
from core.tester import func_case, Tester


async def _write_restart_cache(client: str) -> None:
    session_info = await SessionInfo.assign(
        target_id=f"{client}|Group|1",
        target_from=f"{client}|Group",
        client_name=client,
        owner_peer_id=f"STALE-PEER-{client}",
        sender_id=f"{client}|1",
        create=True,
    )
    author_cache = PrivateData.path / ".cache_restart_author"
    author_cache.write_bytes(orjson.dumps(converter.unstructure(session_info)))
    # load_prompt 会一并读取模块加载结果，该文件由 load_modules 写出，此处补齐以隔离依赖
    loader_cache = PrivateData.path / ".cache_loader"
    if not loader_cache.exists():
        loader_cache.write_text("")


async def _prompt_sent(target_peer: str | None = None) -> bool:
    query = JobQueuesTable.filter(action=PlatformAPI.send_message.name)
    if target_peer is not None:
        query = query.filter(target_peer=target_peer)
    return await query.exists()


async def _reset(client: str) -> None:
    Alive.values.clear()
    await JobQueuesTable.filter(action=PlatformAPI.send_message.name).delete()
    await JobQueuePeersTable.filter(peer_id=f"TEST-PEER-{client}").delete()
    await _write_restart_cache(client)


async def _register_client(client: str, peer_id: str | None = None) -> None:
    metadata = {
        "target_prefix_list": [f"{client}|Group"],
        "sender_prefix_list": [client],
    }
    await JobQueuePeersTable.create(
        peer_id=peer_id or f"TEST-PEER-{client}",
        role="client",
        service=client,
        state="ready",
        capabilities=["rpc", "signals"],
        metadata=metadata,
        heartbeat_at=datetime.now(UTC),
        lease_until=datetime.now(UTC) + timedelta(seconds=300),
    )


def _cleanup(alive: dict) -> None:
    (PrivateData.path / ".cache_restart_author").unlink(missing_ok=True)
    Alive.values.clear()
    Alive.values.update(alive)


async def _test_ignores_previous_client_lease():
    client = "RESTARTC"
    old_peer = f"STALE-PEER-{client}"
    new_peer = f"TEST-PEER-{client}"
    alive = Alive.values.copy()
    try:
        await _reset(client)
        await JobQueuePeersTable.filter(peer_id=old_peer).delete()
        await _register_client(client, old_peer)

        async def _new_instance_comes_online(_delay):
            assert not await _prompt_sent(), "旧实例仍在线时不得提前投递"
            await _register_client(client, new_peer)

        poll_sleep = AsyncMock(side_effect=_new_instance_comes_online)
        with patch("core.server.init.asyncio", SimpleNamespace(sleep=poll_sleep, wait_for=asyncio.wait_for)):
            await load_prompt(None, timeout=10)
        return poll_sleep.await_count == 1 and await _prompt_sent(new_peer) and not await _prompt_sent(old_peer)
    except Exception:
        return False
    finally:
        await JobQueuePeersTable.filter(peer_id=old_peer).delete()
        _cleanup(alive)


async def _test_waits_for_client_to_come_online():
    client = "RESTARTA"
    alive = Alive.values.copy()
    try:
        await _reset(client)

        async def _come_online(_delay):
            assert not await _prompt_sent(), "客户端注册前不得投递"
            await _register_client(client)

        poll_sleep = AsyncMock(side_effect=_come_online)
        with patch("core.server.init.asyncio", SimpleNamespace(sleep=poll_sleep, wait_for=asyncio.wait_for)):
            await load_prompt(None, timeout=10)
        return poll_sleep.await_count == 1 and await _prompt_sent(f"TEST-PEER-{client}")

    except Exception:
        return False
    finally:
        _cleanup(alive)


async def _test_gives_up_when_client_never_online():
    client = "RESTARTB"
    alive = Alive.values.copy()
    try:
        await _reset(client)

        await asyncio.wait_for(load_prompt(None, timeout=0.05), timeout=10)
        # 超时放弃后不应残留缓存，否则下次启动会重复投递
        return not await _prompt_sent() and not (PrivateData.path / ".cache_restart_author").exists()

    except (Exception, asyncio.TimeoutError):
        return False
    finally:
        _cleanup(alive)


async def _test_corrupt_author_cache_is_discarded():
    alive = Alive.values.copy()
    author_cache = PrivateData.path / ".cache_restart_author"
    try:
        author_cache.write_bytes(b"{not valid json")
        await load_prompt(None, timeout=0)
        return not author_cache.exists()
    except Exception:
        return False
    finally:
        _cleanup(alive)


@func_case
async def test_restart_prompt(tester: Tester):
    """core.server.init: 重启提示送达测试"""
    try:
        await tester.test(_test_waits_for_client_to_come_online, "等待客户端上线后投递测试")
        await tester.test(_test_ignores_previous_client_lease, "忽略重启前客户端残留租约测试")
        await tester.test(_test_gives_up_when_client_never_online, "客户端不上线时超时放弃测试")
        await tester.test(_test_corrupt_author_cache_is_discarded, "损坏重启缓存丢弃测试")
    finally:
        await JobQueuePeersTable.filter(peer_id__startswith="TEST-PEER-RESTART").delete()

    return tester
