"""Isolated RPC process used by test_rpc_process; never starts a platform bot."""

import asyncio
import json
import sys
from pathlib import Path


async def main(database_path: str, role: str) -> None:
    from tortoise import Tortoise

    from core.queue.base import JobQueueBase
    from core.queue.errors import RpcRemoteError
    from core.queue.rpc import remote

    class Peer(JobQueueBase):
        name = role

    await Tortoise.init(
        db_url=f"sqlite://{database_path}",
        modules={"models": ["core.database.models"]},
        _enable_global_fallback=True,
    )
    if role == "RPC-B":
        await Tortoise.generate_schemas(safe=True)

    stopped = asyncio.Event()

    @remote("audit.echo", target="RPC-B", timeout=10)
    async def echo(payload: dict) -> dict: ...

    @remote("audit.reverse", target="RPC-A", timeout=10)
    async def reverse(value: int) -> int: ...

    @remote("audit.nested", target="RPC-B", timeout=10)
    async def nested(value: int) -> int: ...

    @remote("audit.fail", target="RPC-B", timeout=10)
    async def fail() -> None: ...

    @remote("audit.stop", target="RPC-B", timeout=10)
    async def stop() -> None: ...

    @echo.bind(Peer)
    async def echo_handler(payload: dict) -> dict:
        return payload

    @reverse.bind(Peer)
    async def reverse_handler(value: int) -> int:
        return value * 2

    @nested.bind(Peer)
    async def nested_handler(value: int) -> int:
        return 1 + await reverse.using(Peer)(value)

    @fail.bind(Peer)
    async def fail_handler() -> None:
        raise ValueError("isolated remote failure")

    @stop.bind(Peer)
    async def stop_handler() -> None:
        stopped.set()

    poller = asyncio.create_task(Peer.check_job_queue())
    try:
        if role == "RPC-B":
            print("RPC_READY", flush=True)
            await asyncio.wait_for(stopped.wait(), timeout=35)
            await Peer.wait_process_tasks()
        else:
            payload = {"empty": [], "false": False, "none": None, "text": "双进程", "nested": {"n": 7}}
            assert await echo.using(Peer)(payload) == payload
            assert await nested.using(Peer)(20) == 41
            results = await asyncio.gather(*(nested.using(Peer)(value) for value in range(8)))
            assert results == [value * 2 + 1 for value in range(8)]
            try:
                await fail.using(Peer)()
            except RpcRemoteError as exc:
                assert exc.remote_type == "ValueError"
                assert "isolated remote failure" in str(exc)
            else:
                raise AssertionError("Remote failure was lost")
            assert await echo.using(Peer)({"after_error": True}) == {"after_error": True}
            await stop.using(Peer)()
            assert not Peer._pending
            print(json.dumps({"rpc_process": "passed", "callbacks": len(results) + 1}), flush=True)
    finally:
        await Peer.cancel_process_tasks()
        poller.cancel()
        await asyncio.gather(poller, return_exceptions=True)
        await Tortoise.close_connections()


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    asyncio.run(main(sys.argv[1], sys.argv[2]))
