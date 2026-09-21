"""数据库事务在进入、退出或批量写入阶段被取消时不得残留连接锁、打开的事务或池连接。"""

import asyncio
import uuid
from types import SimpleNamespace

from tortoise.backends.base.client import TransactionContextPooled
from tortoise.connection import get_connections
from tortoise.transactions import in_transaction

from core.database.models import JobQueuesTable
from core.tester import Tester, func_case

try:
    from tortoise.backends.mysql.client import MySQLClient
except ImportError:  # pragma: no cover - 未安装 MySQL 驱动时跳过相关用例
    MySQLClient = None


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


async def _test_cancelled_pooled_transaction_entry_returns_connection():
    released = []
    rolled_back = asyncio.Event()
    begun = asyncio.Event()

    class FakePool:
        async def acquire(self):
            return "POOLED-CONNECTION"

        async def release(self, connection):
            released.append(connection)

    class FakeParent:
        _pool = FakePool()

    class FakeWrapper:
        connection_name = "default"
        _finalized = False
        _connection = None

        def __init__(self):
            self._parent = FakeParent()

        async def begin(self):
            begun.set()
            await asyncio.sleep(5)

        async def rollback(self):
            rolled_back.set()
            self._finalized = True

    context = TransactionContextPooled(FakeWrapper(), asyncio.Lock())

    async def enter_transaction():
        async with context:
            pass

    task = asyncio.create_task(enter_transaction())
    try:
        await asyncio.wait_for(begun.wait(), timeout=5)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    return released == ["POOLED-CONNECTION"] and rolled_back.is_set()


async def _test_cancelled_mysql_bulk_write_rolls_back():
    if MySQLClient is None:
        return True

    begun = asyncio.Event()
    events = []

    class FakeCursor:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return False

        async def executemany(self, query, values):
            begun.set()
            await asyncio.sleep(5)

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

        async def begin(self):
            events.append("begin")

        async def rollback(self):
            events.append("rollback")

        async def commit(self):
            events.append("commit")

    class FakeAcquire:
        async def __aenter__(self):
            return FakeConnection()

        async def __aexit__(self, *exc_info):
            return False

    class FakeClient:
        capabilities = SimpleNamespace(supports_transactions=True)
        log = SimpleNamespace(debug=lambda *args, **kwargs: None)

        def acquire_connection(self):
            return FakeAcquire()

    task = asyncio.create_task(MySQLClient.execute_many(FakeClient(), "INSERT INTO t VALUES (1)", [[1]]))
    try:
        await asyncio.wait_for(begun.wait(), timeout=5)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    return events == ["begin", "rollback"]


@func_case
async def test_database_transaction_cancel(tester: Tester):
    """事务取消后数据库与连接池仍可用。"""
    await tester.test(_test_cancelled_transaction_entry_keeps_database_usable, "事务开始阶段取消不泄漏连接锁")
    await tester.test(_test_cancelled_bulk_write_leaves_no_open_transaction, "批量写入取消不残留打开的事务")
    await tester.test(_test_cancelled_transaction_exit_leaves_no_open_transaction, "事务结束阶段取消不残留打开的事务")
    await tester.test(_test_cancelled_pooled_transaction_entry_returns_connection, "池化事务进入阶段取消归还连接")
    await tester.test(_test_cancelled_mysql_bulk_write_rolls_back, "MySQL 批量写入取消回滚事务")
    return tester
