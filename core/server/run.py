import asyncio
import signal

from core.constants import Info
from core.logger import Logger
from core.queue.server import JobQueueServer
from core.server.init import init_async
from core.server.terminate import cleanup_sessions


stop_event = asyncio.Event()


def inner_ctrl_c_signal_handler(sig, frame):
    stop_event.set()


signal.signal(signal.SIGINT, inner_ctrl_c_signal_handler)


async def main():
    Logger.info("Starting AkariBot Server...")
    await init_async()
    asyncio.create_task(JobQueueServer.check_job_queue())
    while not stop_event.is_set():
        await asyncio.sleep(1)
    if stop_event.is_set():
        Logger.info("Stopping AkariBot Server...")
        await cleanup_sessions()
        Logger.success("AkariBot Server stopped successfully.")


def run_async(subprocess: bool = False, binary_mode: bool = False):
    import asyncio

    Info.subprocess = subprocess
    Info.binary_mode = binary_mode
    asyncio.run(main())


if __name__ == "__main__":
    run_async()
