"""平台 RPC 实现；普通 ContextManager 方法由共享契约自动绑定。"""

import asyncio
from typing import Any

from core.builtins.message.chain import MessageChain, MessageNodes
from core.builtins.session.context import ContextManager
from core.builtins.session.info import SessionInfo
from core.exports import exports, add_export
from core.logger import Logger
from .base import JobQueueBase
from .contracts import PlatformAPI, ServerAPI
from .rpc import RpcMethod
from .reporting import report_rpc_error


class JobQueueClient(JobQueueBase):
    """平台进程 RPC 消费者及其生命周期。"""

    @classmethod
    async def report_error(cls, method: str, details: str) -> None:
        await report_rpc_error(cls, method, details)


async def resolve_context(session_info: SessionInfo) -> type[ContextManager]:
    """刷新会话信息，并选择常规或主动消息的上下文管理器。"""
    await session_info.refresh_info()
    bot = exports["Bot"]
    slot = bot.fetched_session_ctx_slot if session_info.fetch else session_info.ctx_slot
    return bot.ContextSlots[slot]


for _method in vars(PlatformAPI).values():
    if (
        isinstance(_method, RpcMethod)
        and _method.context_method is not None
        and _method is not PlatformAPI.send_private_msg
    ):
        _method.bind_context(JobQueueClient, resolve_context)


@PlatformAPI.post_message.bind(JobQueueClient)
async def post_message(
    session_info: SessionInfo, message: MessageChain | MessageNodes, module_name: str = ""
) -> list[str]:
    """主动消息未取得消息 ID 时，将剩余下一跳交回服务端。"""
    ctx_manager = await resolve_context(session_info)
    try:
        sent = await ctx_manager.send_message(session_info, message, quote=False)
    except asyncio.CancelledError:
        raise
    except Exception:
        Logger.exception(f"Failed to post message to {session_info.target_id}: ")
        sent = []
    if sent:
        Logger.info(f"Posted message to {session_info.target_id}: {sent}")
        return sent
    next_hops = list(session_info.next_hops or [])
    if not next_hops:
        Logger.warning(f"Failed to post message to {session_info.target_id}, no next hop left.")
        return []
    Logger.warning(f"Failed to post message to {session_info.target_id}, handing over to the next hop.")
    await ServerAPI.post_next_hop.submit(next_hops, message, module_name)
    return []


@PlatformAPI.send_private_msg.bind(JobQueueClient)
async def send_private_msg(session_info: SessionInfo, user_id: str, message: MessageChain | MessageNodes) -> list[str]:
    """保留私信发送失败返回空列表的领域约定。"""
    ctx_manager = await resolve_context(session_info)
    try:
        return await ctx_manager.send_private_msg(session_info, user_id, message)
    except asyncio.CancelledError:
        raise
    except Exception:
        Logger.exception(f"Failed to send private message to {user_id}: ")
        return []


@PlatformAPI.call_onebot_api.bind(JobQueueClient)
async def call_onebot_api(session_info: SessionInfo, api_name: str, **kwargs: Any) -> dict:
    ctx_manager = await resolve_context(session_info)
    call_api = getattr(ctx_manager, "call_onebot_api", None)
    if call_api:
        return await call_api(api_name, **kwargs)
    return {"success": False, "error": "OneBot API not supported in this context"}


add_export(JobQueueClient)
