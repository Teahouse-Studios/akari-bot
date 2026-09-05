"""Real two-process RPC over a temporary SQLite database, without platform SDKs."""

import asyncio
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from core.tester import Tester, func_case


async def _test_bidirectional_process_rpc():
    worker = Path(__file__).resolve().parents[1] / "helpers" / "rpc_worker.py"
    processes = []
    with TemporaryDirectory(prefix="akari-rpc-") as directory:
        database = str(Path(directory) / "queue.sqlite3")
        environment = {**os.environ, "CI": "1", "PYTHONIOENCODING": "UTF-8"}
        try:
            server = await asyncio.create_subprocess_exec(
                sys.executable,
                str(worker),
                database,
                "RPC-B",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=environment,
            )
            processes.append(server)
            # Readiness comes after schema creation, never from a guessed startup delay.
            async with asyncio.timeout(20):
                while True:
                    line = await server.stdout.readline()
                    if not line:
                        raise AssertionError((await server.stderr.read()).decode("utf-8", errors="replace"))
                    if line.strip() == b"RPC_READY":
                        break
            caller = await asyncio.create_subprocess_exec(
                sys.executable,
                str(worker),
                database,
                "RPC-A",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=environment,
            )
            processes.append(caller)
            caller_output, server_output = await asyncio.wait_for(
                asyncio.gather(caller.communicate(), server.communicate()),
                timeout=40,
            )
            for process, output in ((caller, caller_output), (server, server_output)):
                if process.returncode != 0:
                    raise AssertionError(b"\n".join(output).decode("utf-8", errors="replace"))
            return b'"rpc_process": "passed"' in caller_output[0] and b'"callbacks": 9' in caller_output[0]
        finally:
            for process in processes:
                if process.returncode is None:
                    process.kill()
            await asyncio.gather(*(process.wait() for process in processes))


@func_case
async def test_rpc_process(tester: Tester):
    await tester.test(_test_bidirectional_process_rpc, "独立进程 RPC 往返、并发反向调用、错误传播和关闭测试")
    return tester
