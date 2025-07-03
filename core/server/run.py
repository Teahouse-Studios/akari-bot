from core.logger import Logger
from core.queue.server import JobQueueServer
from core.server.init import init_async


async def main():
    Logger.info("Akari Bot Server is starting...")
    await init_async()
    await JobQueueServer.check_job_queue()


def run_async():
    import asyncio

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        Logger.info("Server stopped by user.")
