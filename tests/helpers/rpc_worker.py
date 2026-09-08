"""Isolated RPC process used by test_rpc_process; never starts a platform bot."""

import asyncio
import json
import sys
from pathlib import Path


async def main(database_path: str, role: str) -> None:
    from tortoise import Tortoise

    from core.queue.base import JobQueueBase
    from core.queue.errors import RpcRemoteError
    from core.queue.peer import PeerDirectory, PeerSelector
    from core.queue.rpc import remote

    class Peer(JobQueueBase):
        name = role

    Peer.configure_peer(role="test", service=f"{role}-SERVICE", capabilities=["rpc", "signals"])

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

    @Peer.on_signal("audit.signal")
    async def signal_handler(context, payload):
        return {"receiver": role, "source": context.source_peer_id, "payload": payload}

    poller = asyncio.create_task(Peer.check_job_queue())
    try:
        async with asyncio.timeout(10):
            while not await PeerDirectory.resolve(PeerSelector.peer(role)):
                await asyncio.sleep(0.01)
        if role == "RPC-B":
            print("RPC_READY", flush=True)
            await asyncio.wait_for(stopped.wait(), timeout=35)
            await Peer.wait_process_tasks()
        else:
            async with asyncio.timeout(10):
                while len(await PeerDirectory.resolve(PeerSelector.peer("RPC-A", "RPC-B"))) != 2:
                    await asyncio.sleep(0.01)
            signal_report = await Peer.gather_signal(
                "audit.signal", {"version": 2}, PeerSelector.peer("RPC-B"), timeout=10
            )
            assert signal_report.results["RPC-B"] == [
                {"receiver": "RPC-B", "source": "RPC-A", "payload": {"version": 2}}
            ]
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
            print(
                json.dumps({"rpc_process": "passed", "signals": "passed", "callbacks": len(results) + 1}),
                flush=True,
            )
    finally:
        await Peer.cancel_process_tasks()
        poller.cancel()
        await asyncio.gather(poller, return_exceptions=True)
        await Tortoise.close_connections()


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    asyncio.run(main(sys.argv[1], sys.argv[2]))
