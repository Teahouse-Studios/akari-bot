"""S3 同步 SDK 的异步隔离与超时回归测试。"""

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

from core.tester import Tester, func_case
from core.utils.s3 import S3StorageAPI


async def _test_s3_sync_call_is_bounded_without_blocking_loop():
    storage = object.__new__(S3StorageAPI)
    storage.operation_timeout = 0.03
    storage._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="test-s3")
    loop_progressed = False

    def slow_call():
        time.sleep(0.12)

    async def mark_loop_progress():
        nonlocal loop_progressed
        await asyncio.sleep(0.01)
        loop_progressed = True

    marker = asyncio.create_task(mark_loop_progress())
    started = time.perf_counter()
    timed_out = False
    try:
        await storage._run_sync(slow_call)
    except TimeoutError:
        timed_out = True
    elapsed = time.perf_counter() - started
    await marker
    storage._executor.shutdown(wait=True)
    return timed_out and loop_progressed and elapsed < 0.1


@func_case
async def test_s3_async(tester: Tester):
    await tester.test(_test_s3_sync_call_is_bounded_without_blocking_loop, "S3 卡顿不阻塞事件循环并按时超时")
    return tester
