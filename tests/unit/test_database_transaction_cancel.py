"""SQLite 事务在进入或批量写入阶段被取消时不得残留连接锁与打开的事务。"""

import asyncio
import uuid

from tortoise.connection import get_connections
from tortoise.transactions import in_transaction

from core.database.models import JobQueuesTable
from core.tester import Tester, func_case


def _queue_row() -> JobQueuesTable:
    return JobQueuesTable(
        task_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        source_peer_id="TEST-DB-CANCEL",
        target_peer="TEST-DB-CANCEL",
        action="test",
        args={},
    )


async def _test_cancelled_transaction_entry_keeps_database_usable():
    client = get_connections().get("default")
    raw = client._connection
    original_commit = raw.commit

    async def slow_commit():
        await asyncio.sleep(5)
        return await original_commit()

    async def enter_transaction():
        async with in_transaction("default"):
            pass

    raw.commit = slow_commit
    task = asyncio.create_task(enter_transaction())
    try:
        await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    finally:
        raw.commit = original_commit

    try:
        async with asyncio.timeout(5):
            await JobQueuesTable.all()
    except TimeoutError:
        return False
    return True


async def _test_cancelled_bulk_write_leaves_no_open_transaction():
    raw = get_connections().get("default")._connection
    original_executemany = raw.executemany

    async def slow_executemany(sql, values):
        await asyncio.sleep(5)
        return await original_executemany(sql, values)

    async def bulk_write():
        await JobQueuesTable.bulk_create([_queue_row(), _queue_row()])

    raw.executemany = slow_executemany
    task = asyncio.create_task(bulk_write())
    try:
        await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    finally:
        raw.executemany = original_executemany

    try:
        async with asyncio.timeout(5):
            await JobQueuesTable.bulk_create([_queue_row()])
    except Exception:
        return False
    return True


async def _test_cancelled_transaction_exit_leaves_no_open_transaction():
    raw = get_connections().get("default")._connection
    original_commit = raw.commit
    commits = 0

    async def slow_second_commit():
        nonlocal commits
        commits += 1
        if commits >= 2:
            await asyncio.sleep(5)
        return await original_commit()

    async def run_transaction():
        async with in_transaction("default") as connection:
            await connection.execute_query("SELECT 1")

    raw.commit = slow_second_commit
    task = asyncio.create_task(run_transaction())
    try:
        await asyncio.sleep(0.5)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    finally:
        raw.commit = original_commit

    try:
        async with asyncio.timeout(5):
            await JobQueuesTable.bulk_create([_queue_row()])
    except Exception:
        return False
    return True


@func_case
async def test_database_transaction_cancel(tester: Tester):
    """SQLite 事务取消后数据库仍可用。"""
    await tester.test(_test_cancelled_transaction_entry_keeps_database_usable, "事务开始阶段取消不泄漏连接锁")
    await tester.test(_test_cancelled_bulk_write_leaves_no_open_transaction, "批量写入取消不残留打开的事务")
    await tester.test(_test_cancelled_transaction_exit_leaves_no_open_transaction, "事务结束阶段取消不残留打开的事务")
    return tester
