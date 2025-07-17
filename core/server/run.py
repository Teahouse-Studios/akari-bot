from core.constants import Info
from core.logger import Logger
from core.queue.server import JobQueueServer
from core.server.init import init_async


async def main():
    Logger.info("Akari Bot Server is starting...")
    await init_async()
    await JobQueueServer.check_job_queue()


def run_async(subprocess: bool = False, binary_mode: bool = False):
    import asyncio

    Info.subprocess = subprocess
    Info.binary_mode = binary_mode

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        Logger.info("Server stopped by user.")
