"""Submit configured error reports without waiting on a reverse RPC."""

from core.config.base import CoreConfig
from core.logger import Logger


async def report_rpc_error(peer, method: str, details: str) -> None:
    from .contracts import ServerAPI

    Logger.error(f"RPC {method} failed:\n{details}")
    if CoreConfig.report_targets and method != ServerAPI.report_error.name:
        await ServerAPI.report_error.using(peer).submit(method, details)
