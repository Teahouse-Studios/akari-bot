"""S3 同步 SDK 的异步隔离与超时回归测试。"""

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

from botocore.exceptions import ClientError
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


async def _test_manifest_updater_result_is_written():
    storage = object.__new__(S3StorageAPI)
    storage._manifest_locks = {}
    written = []

    async def read_manifest(_prefix):
        return [{"key": "persist/old"}]

    async def write_manifest(prefix, files):
        written.append((prefix, files))

    storage._read_manifest = read_manifest
    storage._write_manifest = write_manifest

    await storage._update_manifest("persist", lambda files: [f for f in files if f["key"] != "persist/old"])

    async def append_file(files):
        files.append({"key": "temp/new"})

    await storage._update_manifest("temp", append_file)
    return written == [("persist", []), ("temp", [{"key": "persist/old"}, {"key": "temp/new"}])]


async def _test_delete_updates_manifest():
    storage = object.__new__(S3StorageAPI)
    storage._manifest_locks = {}
    manifests = {
        storage.PERSIST_PREFIX: [{"key": "persist/keep"}, {"key": "persist/remove"}],
        storage.TEMP_PREFIX: [{"key": "temp/remove"}, {"key": "temp/keep"}],
    }
    deleted = []

    async def delete_file(key):
        deleted.append(key)
        return True

    async def read_manifest(prefix):
        return list(manifests[prefix])

    async def write_manifest(prefix, files):
        manifests[prefix] = files

    storage.delete_file = delete_file
    storage._read_manifest = read_manifest
    storage._write_manifest = write_manifest

    persist_result = await storage.delete_persist("remove")
    temp_result = await storage.delete_temp("remove")
    return (
        persist_result
        and temp_result
        and deleted == ["persist/remove", "temp/remove"]
        and manifests[storage.PERSIST_PREFIX] == [{"key": "persist/keep"}]
        and manifests[storage.TEMP_PREFIX] == [{"key": "temp/keep"}]
    )


def _client_error(code: str, status: int, operation: str) -> ClientError:
    return ClientError(
        {
            "Error": {"Code": code, "Message": code},
            "ResponseMetadata": {"HTTPStatusCode": status},
        },
        operation,
    )


def _test_manifest_read_only_swallows_not_found():
    storage = object.__new__(S3StorageAPI)
    storage.bucket = "bucket"

    class Client:
        error = _client_error("NoSuchKey", 404, "GetObject")

        def get_object(self, **_kwargs):
            raise self.error

    storage._client = Client()
    if storage._read_manifest_sync("temp") != []:
        return False

    storage._client.error = _client_error("AccessDenied", 403, "GetObject")
    try:
        storage._read_manifest_sync("temp")
    except ClientError as e:
        if e.response["Error"]["Code"] != "AccessDenied":
            return False
    else:
        return False

    storage._client.error = _client_error("InternalError", 500, "GetObject")
    try:
        storage._read_manifest_sync("temp")
    except ClientError as e:
        return e.response["Error"]["Code"] == "InternalError"
    return False


async def _test_key_exists_only_swallows_not_found():
    storage = object.__new__(S3StorageAPI)
    storage.bucket = "bucket"

    class Client:
        error = None

        def head_object(self, **_kwargs):
            if self.error:
                raise self.error
            return {"ContentLength": 1}

    storage._client = Client()

    async def run_sync(func, *args, **kwargs):
        return func(*args, **kwargs)

    storage._run_sync = run_sync
    if not await storage._key_exists("persist/file"):
        return False

    for code, status in (("404", 400), ("NoSuchKey", 400), ("NotFound", 400), ("Unknown", 404)):
        storage._client.error = _client_error(code, status, "HeadObject")
        if await storage._key_exists("persist/file"):
            return False

    for code, status in (("AccessDenied", 403), ("InternalError", 500)):
        storage._client.error = _client_error(code, status, "HeadObject")
        try:
            await storage._key_exists("persist/file")
        except ClientError as e:
            if e.response["Error"]["Code"] != code:
                return False
        else:
            return False
    return True


@func_case
async def test_s3_async(tester: Tester):
    await tester.test(_test_s3_sync_call_is_bounded_without_blocking_loop, "S3 卡顿不阻塞事件循环并按时超时")
    await tester.test(_test_manifest_updater_result_is_written, "S3 manifest updater 的返回值会作为新清单写入")
    await tester.test(_test_delete_updates_manifest, "S3 删除文件后同步移除 manifest 条目")
    await tester.test(_test_manifest_read_only_swallows_not_found, "S3 manifest 读取仅忽略明确的不存在错误")
    await tester.test(_test_key_exists_only_swallows_not_found, "S3 对象存在性检查仅忽略明确的不存在错误")
    return tester
