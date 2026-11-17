"""KOOK 平台客户端的运行与关闭生命周期。"""

import asyncio

from core.client.init import client_cleanup
from core.logger import Logger


async def shutdown(bot) -> None:
    """释放核心客户端，并关闭 khl.py 未提供公开关闭入口的 HTTP Session。"""
    try:
        await client_cleanup()
    except Exception:
        Logger.exception("Failed to clean up KOOK client resources:")

    requester = getattr(getattr(getattr(bot, "client", None), "gate", None), "requester", None)
    session = getattr(requester, "_cs", None)
    if session is not None:
        try:
            await session.close()
        except Exception:
            Logger.exception("Failed to close KOOK SDK HTTP session:")
        finally:
            requester._cs = None


async def run_client(bot) -> None:
    try:
        await bot.start()
    finally:
        await shutdown(bot)


def run_bot(bot) -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run_client(bot))
    finally:
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.run_until_complete(loop.shutdown_default_executor())
        loop.close()
        asyncio.set_event_loop(None)


__all__ = ["run_bot", "run_client", "shutdown"]
