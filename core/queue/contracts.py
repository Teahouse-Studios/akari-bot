"""Shared RPC declarations. Importing this module never loads either receiver.

Platform signatures come directly from ContextManager. A new ordinary platform
capability needs one exposure here and its SDK implementation, with no queue
serializer or receiving handler to maintain. Server services have explicit
contracts because their implementations must stay in the server process.
"""

from typing import Any, Literal

from core.builtins.message.chain import MessageChain, MessageNodes
from core.builtins.session.context import ContextManager
from core.builtins.session.features import Features
from core.builtins.session.info import EventInfo, SessionInfo
from .codec import register_value_type
from .rpc import context_method, remote


register_value_type("message", MessageChain | MessageNodes)
register_value_type("session", SessionInfo)
register_value_type("event", EventInfo)
register_value_type("features", Features)


def _platform_target(args) -> str:
    return args["session_info"].client_name


class PlatformAPI:
    check_native_permission = context_method(ContextManager.check_native_permission)
    send_message = context_method(ContextManager.send_message)
    send_private_msg = context_method(ContextManager.send_private_msg)
    delete_message = context_method(ContextManager.delete_message)
    restrict_member = context_method(ContextManager.restrict_member)
    unrestrict_member = context_method(ContextManager.unrestrict_member)
    kick_member = context_method(ContextManager.kick_member)
    ban_member = context_method(ContextManager.ban_member)
    unban_member = context_method(ContextManager.unban_member)
    grant_permission_group = context_method(ContextManager.grant_permission_group)
    revoke_permission_group = context_method(ContextManager.revoke_permission_group)
    add_reaction = context_method(ContextManager.add_reaction)
    remove_reaction = context_method(ContextManager.remove_reaction)
    start_typing = context_method(ContextManager.start_typing)
    end_typing = context_method(ContextManager.end_typing)
    error_signal = context_method(ContextManager.error_signal)
    hold_context = context_method(ContextManager.hold_context)
    release_context = context_method(ContextManager.release_context)

    @staticmethod
    @remote("platform.post_message", target=_platform_target, timeout=7200)
    async def post_message(
        session_info: SessionInfo, message: MessageChain | MessageNodes, module_name: str = ""
    ) -> list[str]:
        """Post a channel message, handing failed hops back to the server."""
        ...

    @staticmethod
    @remote("platform.call_onebot_api", target=_platform_target)
    async def call_onebot_api(session_info: SessionInfo, api_name: str, **kwargs: Any) -> dict:
        """Call the platform's explicitly supported OneBot extension."""
        ...


class ServerAPI:
    @staticmethod
    @remote("server.report_error")
    async def report_error(method: str, details: str) -> None:
        """Deliver a configured error report from either process."""
        ...

    @staticmethod
    @remote("server.receive_message", timeout=7200)
    async def receive_message(session_info: SessionInfo) -> None:
        """Complete message processing before releasing the originating context."""
        ...

    @staticmethod
    @remote("server.receive_event", timeout=7200)
    async def receive_event(event_info: EventInfo) -> None: ...

    @staticmethod
    @remote("server.keepalive", timeout=30)
    async def keepalive(
        client_name: str,
        target_prefix_list: list[str] | None = None,
        sender_prefix_list: list[str] | None = None,
        ctx_slot_index: int | None = None,
        features: Features | None = None,
    ) -> None: ...

    @staticmethod
    @remote("server.trigger_hook", timeout=7200)
    async def trigger_hook(module_or_hook_name: str, session_info: SessionInfo | None = None, **kwargs: Any) -> Any: ...

    @staticmethod
    @remote("server.direct_message")
    async def direct_message(
        session_info: SessionInfo, message: MessageChain | MessageNodes, disable_secret_check: bool = True
    ) -> None: ...

    @staticmethod
    @remote("server.get_bot_version", timeout=30)
    async def get_bot_version() -> str | None: ...

    @staticmethod
    @remote("server.get_web_render_status", timeout=30)
    async def get_web_render_status() -> bool: ...

    @staticmethod
    @remote("server.get_modules_list", timeout=30)
    async def get_modules_list() -> list[str]: ...

    @staticmethod
    @remote("server.get_modules_info", timeout=30)
    async def get_modules_info(locale: str = "zh_cn") -> dict: ...

    @staticmethod
    @remote("server.get_module_helpdoc", timeout=30)
    async def get_module_helpdoc(module: str, locale: str = "zh_cn") -> dict: ...

    @staticmethod
    @remote("server.get_module_related", timeout=30)
    async def get_module_related(module: str) -> list[str]: ...

    @staticmethod
    @remote("server.post_module_action", timeout=7200)
    async def post_module_action(module: str, action: Literal["load", "unload", "reload"]) -> bool: ...

    @staticmethod
    @remote("server.post_next_hop")
    async def post_next_hop(
        next_hops: list[str], message: MessageChain | MessageNodes, module_name: str = ""
    ) -> bool: ...
