"""服务端 RPC 实现；调用签名与编码由共享契约统一管理。"""

import asyncio
import re
import time
from hashlib import sha256
from typing import TYPE_CHECKING, Any, Literal

from core.alive import Alive
from core.builtins.filter import reload_filter_words as reload_badword_rules
from core.builtins.message.chain import MessageChain, MessageNodes
from core.builtins.message.internal import I18NContext
from core.builtins.parser.command import CommandParser
from core.builtins.parser.message import parser
from core.builtins.session.info import EventInfo, SessionInfo
from core.builtins.utils import command_prefix
from core.constants import Info
from core.constants.path import assets_path
from core.config.base import CoreConfig
from core.exports import exports, add_export
from core.i18n import Locale
from core.loader import ModulesManager
from core.logger import Logger
from core.smtp import send_report
from core.utils.bash import run_sys_command
from core.utils.web_render import (
    ElementScreenshotOptions,
    PageScreenshotOptions,
    SourceOptions,
    StatusOptions,
    check_web_render_status,
    close_web_render,
    enable_web_render,
    init_web_render,
    web_render,
)
from .base import JobQueueBase
from .contracts import PlatformAPI, ProcessAPI, ServerAPI
from .diagnostics import collect_self_usage, gather_process_usage, usage_payload
from .errors import RpcUnavailableError
from .reporting import report_rpc_error

if TYPE_CHECKING:
    from .peer import ServiceRoute


class JobQueueServer(JobQueueBase):
    """服务端 RPC 消费者及其生命周期。"""

    @classmethod
    async def ensure_target_available(cls, target: str, route: "ServiceRoute | None" = None) -> None:
        """以权威 Peer Registry 判断 Client 或实例是否仍可接收新任务。"""
        if target in ("Server", cls.name):
            return
        from .peer import PeerSelector

        # ServiceRoute 已在入队前从 Registry 选中了一个 ready 实例，无需重复查询。
        if route is not None and target != route.service:
            return
        if route is not None:
            records = await cls.registry.resolve(
                PeerSelector(
                    roles=(route.role,) if route.role else (),
                    services=(route.service,),
                )
            )
        else:
            records = await cls.registry.resolve(PeerSelector.peer(target))
            if not records:
                records = await cls.registry.resolve(PeerSelector.service(target))
        if records:
            for record in records:
                cls._update_peer_cache(record.snapshot())
            return
        raise RpcUnavailableError(f"Client or peer {target} is offline.", target=target)

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

    async def send_to_report_target(session, _report) -> None:
        details_chain = await exports["Bot"].Hook.trigger(
            "parser_errors.format_error_detail",
            session_info=session,
            args={"text": details.strip()},
        )
        await ServerAPI.direct_message.submit(
            session,
            MessageChain.assign(I18NContext("error.message.report", command=method, disable_joke=True)) + details_chain,
            disable_secret_check=True,
        )

    await send_report(
        [],
        subject=str(I18NContext("smtp.report.subject.error.rpc", method=method)),
        body=f"{str(I18NContext('error.message.report', command=method))}\n{details.strip()}",
        direct_sender=send_to_report_target,
        targets=CoreConfig.report_targets,
    )


@ServerAPI.post_next_hop.bind(JobQueueServer)
async def post_next_hop(next_hops: list[str], message: MessageChain | MessageNodes, module_name: str = "") -> bool:
    """解析下一跳并交给对应平台；跳表值会缩短。"""
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
    version_path = assets_path / ".version"
    if version_path.exists():
        return version_path.read_text()
    returncode, commit_hash, _ = await run_sys_command(["git", "rev-parse", "HEAD"])
    return f"git:{commit_hash}" if returncode == 0 else None


@ServerAPI.get_web_render_status.bind(JobQueueServer)
async def get_web_render_status() -> bool:
    return await check_web_render_status()


# 渲染测试的单次响应上限：截图按张数、源码按字符数截断，避免一次请求把响应体
# 撑到 WebUI 无法处理的量级。超限只截断，不视为失败。
WEB_RENDER_TEST_MAX_IMAGES = 16
WEB_RENDER_TEST_MAX_SOURCE_CHARS = 200_000
# 渲染测试允许透传的字段；未列出的键一律忽略，避免任意参数进入依赖库的选项模型。
WEB_RENDER_TEST_SCREENSHOT_KEYS = (
    "url",
    "content",
    "css",
    "width",
    "height",
    "locale",
    "output_type",
    "output_quality",
    "counttime",
    "stealth",
    "wait_until",
    "wait_after_load",
)
WEB_RENDER_TEST_SOURCE_KEYS = ("url", "locale", "stealth", "wait_until", "wait_after_load", "raw_text")


def _web_render_status_payload(status: dict | None) -> dict | None:
    if not isinstance(status, dict):
        return None
    contexts = []
    raw_contexts = status.get("contexts_open_sorted")
    if isinstance(raw_contexts, dict):
        for index, pages in enumerate(raw_contexts.values()):
            contexts.append({"index": index, "pages": [str(page) for page in pages] if isinstance(pages, list) else []})
    return {
        "available": bool(status.get("browser_initialized") or status.get("remote_configured")),
        "browser_initialized": bool(status.get("browser_initialized")),
        "browser_mode": status.get("browser_mode"),
        "headless": bool(status.get("headless")),
        "keep_pages_open": bool(status.get("keep_pages_open")),
        "debug_mode": bool(status.get("debug_mode")),
        "remote_only": bool(status.get("remote_only")),
        "remote_configured": bool(status.get("remote_configured")),
        "remote_timeout": status.get("remote_timeout"),
        "export_logs": bool(status.get("export_logs")),
        "logs_path": status.get("logs_path"),
        "name": status.get("name"),
        "contexts": contexts,
        "contexts_total": status.get("contexts_total"),
        "leaked": bool(status.get("leaked")),
    }


async def _web_render_status_detail() -> dict | None:
    try:
        status = await web_render.status(StatusOptions())
    except asyncio.CancelledError:
        raise
    except Exception:
        Logger.exception("Failed to read WebRender status for WebUI.")
        return None
    # 本地浏览器未就绪且未配置远端时，依赖库直接返回 None；此时仍给出未就绪的状态，
    # 让前端能区分「读不到状态」与「浏览器没起来」。
    return _web_render_status_payload(status if status is not None else {"browser_initialized": False})


@ServerAPI.get_runtime_stats.bind(JobQueueServer)
async def get_runtime_stats() -> dict:
    backend_name = getattr(JobQueueServer.backend, "name", None)
    return {
        "jobqueue_backend": backend_name if isinstance(backend_name, str) and backend_name else None,
        "command_parsed": int(Info.command_parsed or 0),
        "message_parsed": int(Info.message_parsed or 0),
    }


@ServerAPI.get_process_usage.bind(JobQueueServer)
async def get_process_usage() -> dict:
    try:
        usages, failures = await gather_process_usage()
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        Logger.exception("Failed to gather process usage for WebUI.")
        return {"items": [], "failures": [], "error": type(exc).__name__}
    payload = usage_payload(usages, failures)
    payload["error"] = None
    return payload


@ServerAPI.get_web_render_status_detail.bind(JobQueueServer)
async def get_web_render_status_detail() -> dict | None:
    return await _web_render_status_detail()


@ServerAPI.control_web_render.bind(JobQueueServer)
async def control_web_render(action: Literal["start", "stop", "restart"]) -> dict:
    if action not in ("start", "stop", "restart"):
        return {"ok": False, "error": "invalid_action", "status": None}
    try:
        if action in ("stop", "restart"):
            await close_web_render()
        # stop 只需浏览器已按请求关闭；start / restart 则以依赖库的初始化结果为准。
        ok = True
        if action in ("start", "restart"):
            ok = bool(await init_web_render())
        Info.web_render_status = await check_web_render_status()
    except asyncio.CancelledError:
        raise
    except Exception:
        Logger.exception(f"Failed to {action} WebRender for WebUI.")
        Info.web_render_status = False
        return {"ok": False, "error": "control_failed", "status": None}
    return {
        "ok": ok,
        "error": None if ok else "init_failed",
        "status": await _web_render_status_detail(),
    }


def _web_render_test_failure(mode: str | None, error: str, started: float) -> dict:
    return {
        "ok": False,
        "mode": mode,
        "elapsed": round(time.monotonic() - started, 3),
        "status": None,
        "source": None,
        "source_truncated": False,
        "images": [],
        "output_type": None,
        "error": error,
    }


@ServerAPI.test_web_render.bind(JobQueueServer)
async def test_web_render(options: dict) -> dict:
    started = time.monotonic()

    def elapsed() -> float:
        return round(time.monotonic() - started, 3)

    if not isinstance(options, dict):
        return _web_render_test_failure(None, "invalid_options", started)
    mode = options.get("mode") or "status"
    if mode not in ("status", "source", "screenshot"):
        return _web_render_test_failure(mode if isinstance(mode, str) else None, "invalid_mode", started)
    if not enable_web_render:
        return _web_render_test_failure(mode, "web_render_disabled", started)

    status = await _web_render_status_detail()
    if mode == "status":
        # 只探测可用性：不渲染任何页面，供前端的「测试连接」按钮使用。
        ok = bool(status and status.get("available"))
        return {
            "ok": ok,
            "mode": mode,
            "elapsed": elapsed(),
            "status": status,
            "source": None,
            "source_truncated": False,
            "images": [],
            "output_type": None,
            "error": None if ok else "browser_unavailable",
        }

    if mode == "source":
        source_args = {key: options[key] for key in WEB_RENDER_TEST_SOURCE_KEYS if options.get(key) is not None}
        if not source_args.get("url"):
            return _web_render_test_failure(mode, "missing_target", started)
        try:
            source = await web_render.source(SourceOptions(**source_args))
        except ValueError:
            return _web_render_test_failure(mode, "invalid_options", started)
        except asyncio.CancelledError:
            raise
        except Exception:
            Logger.exception("WebRender source test failed.")
            return _web_render_test_failure(mode, "render_failed", started)
        if not isinstance(source, str):
            return _web_render_test_failure(mode, "render_failed", started)
        return {
            "ok": True,
            "mode": mode,
            "elapsed": elapsed(),
            "status": status,
            "source": source[:WEB_RENDER_TEST_MAX_SOURCE_CHARS],
            "source_truncated": len(source) > WEB_RENDER_TEST_MAX_SOURCE_CHARS,
            "images": [],
            "output_type": None,
            "error": None,
        }

    screenshot_args = {key: options[key] for key in WEB_RENDER_TEST_SCREENSHOT_KEYS if options.get(key) is not None}
    if not screenshot_args.get("url") and not screenshot_args.get("content"):
        return _web_render_test_failure(mode, "missing_target", started)
    element = options.get("element")
    try:
        if element:
            images = await web_render.element_screenshot(ElementScreenshotOptions(element=element, **screenshot_args))
        else:
            images = await web_render.page_screenshot(PageScreenshotOptions(**screenshot_args))
    except ValueError:
        return _web_render_test_failure(mode, "invalid_options", started)
    except asyncio.CancelledError:
        raise
    except Exception:
        Logger.exception("WebRender screenshot test failed.")
        return _web_render_test_failure(mode, "render_failed", started)
    rendered = [image for image in images if isinstance(image, str)] if isinstance(images, list) else []
    if not rendered:
        return _web_render_test_failure(mode, "render_failed", started)
    return {
        "ok": True,
        "mode": mode,
        "elapsed": elapsed(),
        "status": status,
        # 与依赖库一致，images 为裸 base64，data URL 前缀由前端自行拼接。
        "images": rendered[:WEB_RENDER_TEST_MAX_IMAGES],
        "source": None,
        "source_truncated": False,
        "output_type": screenshot_args.get("output_type", "jpeg"),
        "error": None,
    }


@ServerAPI.reload_filter_words.bind(JobQueueServer)
async def reload_filter_words() -> bool:
    try:
        reload_badword_rules()
    except Exception:
        # 词库文件可能正被手工编辑；失败时保留旧词库并如实回报，不中断服务端。
        Logger.exception("Failed to reload filter words: ")
        return False
    return True


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


@ProcessAPI.resource_usage.bind(JobQueueServer)
async def resource_usage() -> dict[str, int]:
    return collect_self_usage()


add_export(JobQueueServer)
