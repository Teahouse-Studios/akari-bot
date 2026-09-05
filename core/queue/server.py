"""服务端 RPC 实现；调用签名与编码由共享契约统一管理。"""

import re
import time
from hashlib import sha256
from typing import Any, Literal

from core.alive import Alive
from core.builtins.message.chain import MessageChain, MessageNodes
from core.builtins.message.internal import I18NContext, Plain
from core.builtins.parser.command import CommandParser
from core.builtins.parser.message import parser
from core.builtins.session.features import Features
from core.builtins.session.info import EventInfo, SessionInfo
from core.builtins.utils import command_prefix
from core.constants.path import PrivateAssets
from core.config.base import CoreConfig
from core.exports import exports, add_export
from core.i18n import Locale
from core.loader import ModulesManager
from core.logger import Logger
from core.utils.bash import run_sys_command
from core.utils.web_render import check_web_render_status
from .base import JobQueueBase
from .contracts import PlatformAPI, ServerAPI
from .errors import RpcUnavailableError
from .reporting import report_rpc_error


class JobQueueServer(JobQueueBase):
    """服务端 RPC 消费者及其生命周期。"""

    @classmethod
    def validate_target(cls, target: str) -> None:
        super().validate_target(target)
        if target not in ("Server", cls.name) and not Alive.is_alive(target):
            raise RpcUnavailableError(f"Client {target} is offline.", target=target)

    @classmethod
    async def report_error(cls, method: str, details: str) -> None:
        await report_rpc_error(cls, method, details)


_recent_reports: dict[str, float] = {}


@ServerAPI.report_error.bind(JobQueueServer)
async def report_error(method: str, details: str) -> None:
    # Reporting itself may fail at the platform. Deduplicate before submitting
    # another send, so identical SDK failures cannot create a reporting loop.
    now = time.monotonic()
    expired = [key for key, timestamp in _recent_reports.items() if now - timestamp > 60]
    for key in expired:
        del _recent_reports[key]
    fingerprint = sha256(f"{method}\n{details}".encode()).hexdigest()
    if fingerprint in _recent_reports:
        return
    if len(_recent_reports) >= 128:
        del _recent_reports[next(iter(_recent_reports))]
    _recent_reports[fingerprint] = now
    bot = exports["Bot"]
    for session in await bot.pick_channel_heads(await bot.fetch_union_target_list(CoreConfig.report_targets)):
        await ServerAPI.direct_message.submit(
            session,
            MessageChain.assign(
                [
                    I18NContext("error.message.report", command=method),
                    Plain(details.strip(), disable_joke=True, allow_parse=False),
                ]
            ),
            disable_secret_check=True,
        )


@ServerAPI.post_next_hop.bind(JobQueueServer)
async def post_next_hop(next_hops: list[str], message: MessageChain | MessageNodes, module_name: str = "") -> bool:
    """解析下一跳并交给对应平台；跳表只会缩短。"""
    bot = exports["Bot"]
    remaining = list(next_hops)
    while remaining:
        target_id = remaining.pop(0)
        session_info = await bot.fetch_target(target_id)
        if not session_info:
            Logger.warning(f"Failed to fetch next hop {target_id}, skipping to the one after it.")
            continue
        if not Alive.is_alive(session_info.client_name):
            Logger.warning(f"Client {session_info.client_name} is offline, skipping next hop {target_id}.")
            continue
        session_info.next_hops = remaining
        Logger.info(f"Post message failed, falling back to next hop {target_id}.")
        try:
            await PlatformAPI.post_message.submit(session_info, message, module_name)
        except RpcUnavailableError:
            continue
        return True
    Logger.warning("Post message failed on every hop of the channel.")
    return False


@ServerAPI.receive_message.bind(JobQueueServer)
async def receive_message(session_info: SessionInfo) -> None:
    await parser(await exports["Bot"].MessageSession.from_session_info(session_info))


@ServerAPI.receive_event.bind(JobQueueServer)
async def receive_event(event_info: EventInfo) -> None:
    await event_info.refresh_info()
    await ModulesManager.dispatch_event(event_info)


@ServerAPI.keepalive.bind(JobQueueServer)
async def keepalive(
    client_name: str,
    target_prefix_list: list[str] | None = None,
    sender_prefix_list: list[str] | None = None,
    ctx_slot_index: int | None = None,
    features: Features | None = None,
) -> None:
    Alive.refresh_alive(
        client_name,
        target_prefix_list=target_prefix_list or [],
        sender_prefix_list=sender_prefix_list or [],
        ctx_slot_index=ctx_slot_index,
        features=features,
    )


@ServerAPI.trigger_hook.bind(JobQueueServer)
async def trigger_hook(module_or_hook_name: str, session_info: SessionInfo | None = None, **kwargs: Any) -> Any:
    if session_info is not None:
        await session_info.refresh_info()
    result = await exports["Bot"].Hook.trigger(module_or_hook_name, session_info=session_info, args=kwargs)
    Logger.trace(f"Trigger hook {module_or_hook_name} with args {kwargs}, result: {result}, type: {type(result)}")
    return result


@ServerAPI.direct_message.bind(JobQueueServer)
async def direct_message(
    session_info: SessionInfo, message: MessageChain | MessageNodes, disable_secret_check: bool = True
) -> None:
    await session_info.refresh_info()
    await exports["Bot"].send_direct_message(session_info, message, disable_secret_check=disable_secret_check)


@ServerAPI.get_bot_version.bind(JobQueueServer)
async def get_bot_version() -> str | None:
    version_path = PrivateAssets.path / ".version"
    if version_path.exists():
        return version_path.read_text()
    returncode, commit_hash, _ = await run_sys_command(["git", "rev-parse", "HEAD"])
    return f"git:{commit_hash}" if returncode == 0 else None


@ServerAPI.get_web_render_status.bind(JobQueueServer)
async def get_web_render_status() -> bool:
    return await check_web_render_status()


@ServerAPI.get_modules_list.bind(JobQueueServer)
async def get_modules_list() -> list[str]:
    modules = (module.to_dict() for module in ModulesManager.return_modules_list(use_cache=False).values())
    return [module["module_name"] for module in modules if module.get("load", True) and not module.get("base", False)]


@ServerAPI.get_modules_info.bind(JobQueueServer)
async def get_modules_info(locale: str = "zh_cn") -> dict:
    modules = {key: module.to_dict() for key, module in ModulesManager.return_modules_list(use_cache=False).items()}
    modules = {key: module for key, module in modules.items() if module.get("load", True)}
    for module in modules.values():
        if module.get("desc"):
            module["desc"] = Locale(locale).t_str(module["desc"])
    return modules


@ServerAPI.get_module_helpdoc.bind(JobQueueServer)
async def get_module_helpdoc(module: str, locale: str = "zh_cn") -> dict:
    module_obj = ModulesManager.modules.get(module)
    if module_obj is None:
        return {}
    help_doc = {"module_name": module_obj.module_name}
    module_info = module_obj.to_dict()
    if module_info.get("desc"):
        help_doc["desc"] = Locale(locale).t_str(module_info["desc"])
    command_parser = CommandParser(
        module_obj, module_name=module_obj.module_name, command_prefixes=[command_prefix[0]], is_superuser=True
    )
    help_doc["commands"] = command_parser.return_json_help_doc(locale)
    regex_help = []
    for regex in module_obj.regex_list.get(show_required_superuser=True) or []:
        pattern = regex.pattern if isinstance(regex.pattern, str) else None
        if isinstance(regex.pattern, re.Pattern):
            pattern = regex.pattern.pattern
        if pattern:
            desc = Locale(locale).t_str(regex.desc) if regex.desc else regex.desc
            regex_help.append({"pattern": pattern, "desc": desc})
    help_doc["regexp"] = regex_help
    return help_doc


@ServerAPI.get_module_related.bind(JobQueueServer)
async def get_module_related(module: str) -> list[str]:
    return ModulesManager.search_related_module(module, include_self=False)


@ServerAPI.post_module_action.bind(JobQueueServer)
async def post_module_action(module: str, action: Literal["load", "unload", "reload"]) -> bool:
    match action:
        case "reload":
            status, _ = await ModulesManager.reload_module(module)
        case "load":
            status = await ModulesManager.load_module(module)
        case "unload":
            status = await ModulesManager.unload_module(module)
        case _:
            status = False
    return status


add_export(JobQueueServer)
