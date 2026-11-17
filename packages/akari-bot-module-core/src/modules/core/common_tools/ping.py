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
    usages, failures = await gather_process_usage()
    if not usages and not failures:
        return []
    locale = msg.session_info.locale
    # 平台名与 jobqueue-hub 为专有名词，仅占位标签需本地化。
    labels = {
        DAEMON_LABEL: "core.message.about.status.process.daemon",
        PEERS_LABEL: "core.message.about.status.process.peers",
    }

    def display_name(name: str) -> str:
        return locale.t(labels[name]) if name in labels else name

    lines = []
    for usage in usages:
        lines.append(
            locale.t(
                "core.message.about.status.process",
                name=display_name(usage.name),
                pid=usage.pid if usage.pid is not None else "-",
                memory=int(usage.memory / (1024 * 1024)),
                metric=usage.metric,
            )
        )
    for failure in failures:
        lines.append(
            locale.t(
                "core.message.about.status.process.unavailable",
                name=display_name(failure.name),
                reason=failure.reason,
            )
        )
    return lines


def _format_running_time() -> str:
    td_seconds = time.time() - started_time
    return f"{int(td_seconds // 3600):02d}:{int((td_seconds % 3600) // 60):02d}:{int(td_seconds % 60):02d}"


def _format_status_result(msg: Bot.MessageSession, result: MessageChain) -> MessageChain:
    if not msg.session_info.support_markdown:
        return result

    rendered = result.as_sendable(msg.session_info)
    body = rendered.to_str(connector="\n")
    return MessageChain.assign(Markdown(f"```\n{body}\n```", disable_joke=True, allow_parse=False))


@about.command("ping {{I18N:core.help.about.ping}}")
async def _(msg: Bot.MessageSession):
    result = MessageChain.assign(Plain("Pong!"))
    result.append(
        I18NContext(
            "core.message.about.ping",
            bot_running_time=_format_running_time(),
            cpu_percent=psutil.cpu_percent(),
            ram_percent=psutil.virtual_memory().percent,
            disk_percent=psutil.disk_usage("/").percent,
            disable_joke=True,
        )
    )
    await msg.finish(result)


@about.command("status {{I18N:core.help.about.status}}", required_superuser=True)
async def _(msg: Bot.MessageSession):
    from core.queue.server import JobQueueServer

    disk = psutil.disk_usage("/")
    result = MessageChain.assign(
        I18NContext(
            "core.message.about.status.detail",
            system_boot_time=str(FormattedTime(psutil.boot_time(), simple=True)),
            bot_running_time=_format_running_time(),
            python_version=platform.python_version(),
            web_render_status=str(Bot.Info.web_render_status),
            jobqueue_backend=JobQueueServer.backend.name,
            client_name=msg.session_info.client_name,
            command_parsed=Bot.Info.command_parsed,
            parsed=Bot.Info.message_parsed,
            cpu_brand=get_cpu_info()["brand_raw"],
            cpu_percent=psutil.cpu_percent(),
            ram=int(psutil.virtual_memory().total / (1024 * 1024)),
            ram_percent=psutil.virtual_memory().percent,
            swap=int(psutil.swap_memory().total / (1024 * 1024)),
            swap_percent=psutil.swap_memory().percent,
            disk_space=int(disk.used / (1024 * 1024 * 1024)),
            disk_space_total=int(disk.total / (1024 * 1024 * 1024)),
            disable_joke=True,
        )
    )
    if process_lines := await _build_process_usage_lines(msg):
        header = msg.session_info.locale.t("core.message.about.status.process.list")
        result.append(Plain("\n".join([header, *process_lines]), disable_joke=True, allow_parse=False))
    await msg.finish(_format_status_result(msg, result))
