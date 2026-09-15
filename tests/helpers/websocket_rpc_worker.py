"""WebSocket JobQueue 独立进程测试工作节点。"""

import asyncio
import json
import sys
from pathlib import Path


async def main(url: str, role: str, token: str) -> None:
    from core.queue.base import JobQueueBase
    from core.queue.errors import RpcRemoteError
    from core.queue.peer import PeerSelector
    from core.queue.rpc import remote
    from core.queue.websocket import WebSocketJobQueueBackend, WebSocketSettings

    settings = WebSocketSettings(url=url, token=token, command_timeout=5, heartbeat_seconds=2)

    class Peer(JobQueueBase):
        name = role
        POLL_INTERVAL_SECONDS = 0.005
        backend = WebSocketJobQueueBackend(settings)

    Peer.configure_peer(role="test", service=f"{role}-SERVICE", node_id=f"{role}-NODE")
    stopped = asyncio.Event()

    @remote("websocket.audit.echo", target="WS-RPC-B", timeout=5)
    async def echo(payload: dict) -> dict: ...

    @remote("websocket.audit.reverse", target="WS-RPC-A", timeout=5)
    async def reverse(value: int) -> int: ...

    @remote("websocket.audit.nested", target="WS-RPC-B", timeout=5)
    async def nested(value: int) -> int: ...

    @remote("websocket.audit.fail", target="WS-RPC-B", timeout=5)
    async def fail() -> None: ...

    @remote("websocket.audit.stop", target="WS-RPC-B", timeout=5)
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
        raise ValueError("isolated WebSocket remote failure")

    @stop.bind(Peer)
    async def stop_handler() -> None:
        stopped.set()

    @Peer.on_signal("websocket.audit.signal")
    async def signal_handler(context, payload):
        return {"receiver": role, "source": context.source_peer_id, "payload": payload}

    poller = asyncio.create_task(Peer.check_job_queue())
    try:
        await Peer.wait_ready(timeout=10)
        if role == "WS-RPC-B":
            print("WS_RPC_READY", flush=True)
            await asyncio.wait_for(stopped.wait(), timeout=30)
            await Peer.wait_process_tasks()
        else:
            async with asyncio.timeout(10):
                while len(await Peer.registry.resolve(PeerSelector.peer("WS-RPC-A", "WS-RPC-B"))) != 2:
                    await asyncio.sleep(0.01)
            signal_report = await Peer.gather_signal(
                "websocket.audit.signal", {"version": 3}, PeerSelector.peer("WS-RPC-B"), timeout=5
            )
            assert signal_report.results["WS-RPC-B"] == [
                {"receiver": "WS-RPC-B", "source": "WS-RPC-A", "payload": {"version": 3}}
            ]
            payload = {"empty": [], "false": False, "none": None, "text": "WebSocket 双进程"}
            assert await echo.using(Peer)(payload) == payload
            assert await nested.using(Peer)(20) == 41
            results = await asyncio.gather(*(nested.using(Peer)(value) for value in range(6)))
            assert results == [value * 2 + 1 for value in range(6)]
            try:
                await fail.using(Peer)()
            except RpcRemoteError as exc:
                assert exc.remote_type == "ValueError"
                assert "isolated WebSocket remote failure" in str(exc)
            else:
                raise AssertionError("WebSocket remote failure was lost")
            await stop.using(Peer)()
            assert not Peer._pending
            print(
                json.dumps({"websocket_rpc_process": "passed", "signals": "passed", "callbacks": 7}),
                flush=True,
            )
    finally:
        await Peer.begin_shutdown()
        await Peer.cancel_process_tasks()
        poller.cancel()
        await asyncio.gather(poller, return_exceptions=True)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    asyncio.run(main(sys.argv[1], sys.argv[2], sys.argv[3]))
