"""SQLite 事务在进入阶段被取消时不得泄漏连接锁。"""

import asyncio

from tortoise.connection import get_connections
from tortoise.transactions import in_transaction

from core.database.models import JobQueuesTable
from core.tester import Tester, func_case


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


@func_case
async def test_database_transaction_cancel(tester: Tester):
    """SQLite 事务入口被取消后数据库仍可用。"""
    await tester.test(_test_cancelled_transaction_entry_keeps_database_usable, "事务开始阶段取消不泄漏连接锁")
    return tester
