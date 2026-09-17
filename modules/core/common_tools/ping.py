import platform
import time

import psutil
from cpuinfo import get_cpu_info

from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import FormattedTime, I18NContext, Markdown, Plain
from core.queue.diagnostics import DAEMON_LABEL, PEERS_LABEL, gather_process_usage
from modules.core.common_tools.about import about

started_time = time.time()


async def _build_process_usage_lines(msg: Bot.MessageSession) -> list[str]:
    """构造各进程内存占用的展示行；无任何数据时返回空列表。"""
    usages, failures = await gather_process_usage()
    if not usages and not failures:
        return []
    locale = msg.session_info.locale
    # 平台名与 jobqueue-hub 为专有名词，仅占位标签需本地化。
    labels = {
        DAEMON_LABEL: "core.message.ping.process.daemon",
        PEERS_LABEL: "core.message.ping.process.peers",
    }

    def display_name(name: str) -> str:
        return locale.t(labels[name]) if name in labels else name

    lines = []
    for usage in usages:
        lines.append(
            locale.t(
                "core.message.ping.process",
                name=display_name(usage.name),
                pid=usage.pid if usage.pid is not None else "-",
                memory=int(usage.memory / (1024 * 1024)),
                metric=usage.metric,
            )
        )
    for failure in failures:
        lines.append(
            locale.t(
                "core.message.ping.process.unavailable",
                name=display_name(failure.name),
                reason=failure.reason,
            )
        )
    return lines


def _format_ping_result(msg: Bot.MessageSession, result: MessageChain) -> MessageChain:
    """在支持 Markdown 的平台将 ping 信息整理到代码块中。"""
    if not msg.session_info.support_markdown:
        return result

    rendered = result.as_sendable(msg.session_info)
    body = rendered.to_str(connector="\n")
    return MessageChain.assign(Markdown(f"```\n{body}\n```", disable_joke=True, allow_parse=False))


@about.command("ping {{I18N:core.help.ping}}")
async def _(msg: Bot.MessageSession):
    from core.queue.server import JobQueueServer

    result = MessageChain.assign(Plain("Pong!"))

    td_seconds = time.time() - started_time
    timediff = f"{int(td_seconds // 3600):02d}:{int((td_seconds % 3600) // 60):02d}:{int(td_seconds % 60):02d}"
    cpu_percent = psutil.cpu_percent()
    ram_percent = psutil.virtual_memory().percent
    if msg.check_super_user():
        boot_start = str(FormattedTime(psutil.boot_time(), simple=True))
        web_render_status = str(Bot.Info.web_render_status)
        ram = int(psutil.virtual_memory().total / (1024 * 1024))
        swap = int(psutil.swap_memory().total / (1024 * 1024))
        swap_percent = psutil.swap_memory().percent
        disk = int(psutil.disk_usage("/").used / (1024 * 1024 * 1024))
        disk_total = int(psutil.disk_usage("/").total / (1024 * 1024 * 1024))
        result.append(
            I18NContext(
                "core.message.ping.detail",
                system_boot_time=boot_start,
                bot_running_time=timediff,
                python_version=platform.python_version(),
                web_render_status=web_render_status,
                jobqueue_backend=JobQueueServer.backend.name,
                cpu_brand=get_cpu_info()["brand_raw"],
                cpu_percent=cpu_percent,
                ram=ram,
                ram_percent=ram_percent,
                swap=swap,
                swap_percent=swap_percent,
                disk_space=disk,
                disk_space_total=disk_total,
                client_name=msg.session_info.client_name,
                command_parsed=Bot.Info.command_parsed,
                parsed=Bot.Info.message_parsed,
                disable_joke=True,
            )
        )
        if process_lines := await _build_process_usage_lines(msg):
            header = msg.session_info.locale.t("core.message.ping.process.list")
            result.append(Plain("\n".join([header, *process_lines]), disable_joke=True, allow_parse=False))
    else:
        disk_percent = psutil.disk_usage("/").percent
        result.append(
            I18NContext(
                "core.message.ping.simple",
                bot_running_time=timediff,
                cpu_percent=cpu_percent,
                ram_percent=ram_percent,
                disk_percent=disk_percent,
                disable_joke=True,
            )
        )
    await msg.finish(_format_ping_result(msg, result))
