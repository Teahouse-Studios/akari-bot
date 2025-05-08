import asyncio

from core.bot_init import init_async
from core.queue_ import check_job_queue


async def main():
    await init_async()

    while True:
        await check_job_queue("Server")
        await asyncio.sleep(1)
