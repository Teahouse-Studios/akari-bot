"""进程内存占用采集。

``uss`` 仅在进程自测时可靠可得：macOS 不向非特权进程开放 ``task_for_pid``，跨进程读取
必然 ``AccessDenied``。故各 Peer 经 ``process.resource_usage`` 信号自报，守护进程与内置
Hub 等非 Peer 进程由 Server 按 PID 读取并降级为 ``rss``。
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

import psutil

from core.logger import Logger

# 非 Peer 进程以固定标签标识，本地化由展示层处理。
DAEMON_LABEL = "daemon"
HUB_LABEL = "jobqueue-hub"
# 扇出整体失败时的占位标签，避免与进程不存在相混淆。
PEERS_LABEL = "peers"

# ping 为公开命令，缓存以抑制连续调用引发的重复扇出。
USAGE_CACHE_TTL_SECONDS = 5
# 避免单个无响应进程将 ping 拖至信号默认超时（30 秒）。
USAGE_GATHER_TIMEOUT_SECONDS = 3
# 失败原因来自远端异常消息，截断以限制单个进程对回复长度的影响。
REASON_MAX_LENGTH = 120


@dataclass(frozen=True)
class ProcessUsage:
    """单个进程的内存占用。``memory`` 为字节，``metric`` 说明其口径。"""

    name: str
    pid: int | None
    memory: int
    metric: str
    threads: int | None = None


@dataclass(frozen=True)
class ProcessUnavailable:
    """未能取得内存占用的进程及其原因。"""

    name: str
    reason: str


def collect_self_usage() -> dict[str, int]:
    """采集当前进程的内存指标；``uss`` 不可得时不写该键，由调用方回落至 ``rss``。"""
    process = psutil.Process()
    usage = {
        "pid": process.pid,
        "rss": process.memory_info().rss,
        "threads": process.num_threads(),
    }
    try:
        usage["uss"] = process.memory_full_info().uss
    except (psutil.Error, OSError):
        # 容器内 smaps 缺失等场景下自测亦可能失败，回落而非报错。
        pass
    return usage


def collect_external_usage(pid: int | None) -> dict[str, int] | None:
    """按 PID 读取同机其他进程的内存指标；进程不存在或不可读时返回 None。

    仅取 ``rss``：跨进程 ``uss`` 在 Linux 可得而在 macOS 必然失败，机会性获取将使同一份
    输出的口径随平台漂移。
    """
    if not pid:
        return None
    try:
        process = psutil.Process(pid)
        return {
            "pid": pid,
            "rss": process.memory_info().rss,
            "threads": process.num_threads(),
        }
    except (psutil.Error, OSError):
        return None


def build_usage(name: str, usage: dict[str, int]) -> ProcessUsage | None:
    """将原始指标转为展示行；缺少可用指标的载荷视为无效。"""
    memory = usage.get("uss")
    metric = "USS"
    if not isinstance(memory, int):
        memory = usage.get("rss")
        metric = "RSS"
    if not isinstance(memory, int):
        return None
    pid = usage.get("pid")
    threads = usage.get("threads")
    return ProcessUsage(
        name=name,
        pid=pid if isinstance(pid, int) else None,
        memory=memory,
        metric=metric,
        threads=threads if isinstance(threads, int) else None,
    )


def summarize_process_usage(
    results: dict[str, list],
    errors: dict[str, str],
    peers: dict[str, dict],
) -> tuple[list[ProcessUsage], list[ProcessUnavailable]]:
    """将信号扇出的逐实例结果整理为按 service 名排序的展示行。

    :param results: ``SignalReport.results``，即 ``peer_id`` 到各本地订阅者返回值的映射
    :param errors: ``SignalReport.errors``，即 ``peer_id`` 到失败原因的映射
    :param peers: ``Alive.values`` 快照，用于将 ``peer_id`` 还原为 service 名
    """

    def display_name(peer_id: str) -> str:
        data = peers.get(peer_id) or {}
        service = data.get("service") or data.get("client_name")
        return service if isinstance(service, str) and service else peer_id

    usages = []
    failures = []
    for peer_id, values in results.items():
        name = display_name(peer_id)
        usage = None
        for value in values:
            if isinstance(value, dict):
                usage = build_usage(name, value)
            if usage is not None:
                break
        if usage is None:
            # 载荷无效者仍须列出，否则该进程将从输出中消失。
            failures.append(ProcessUnavailable(name, "invalid"))
            continue
        usages.append(usage)
    for peer_id, reason in errors.items():
        failures.append(ProcessUnavailable(display_name(peer_id), str(reason)[:REASON_MAX_LENGTH]))
    usages.sort(key=lambda usage: (usage.name, usage.pid or 0))
    failures.sort(key=lambda failure: failure.name)
    return usages, failures


_usage_cache: tuple[float, list[ProcessUsage], list[ProcessUnavailable]] | None = None
_usage_lock = asyncio.Lock()


async def gather_process_usage(
    use_cache: bool = True,
) -> tuple[list[ProcessUsage], list[ProcessUnavailable]]:
    """汇总各进程的内存占用。

    Peer 经信号自报；守护进程与内置 Hub 由当前进程按 PID 读取，仅在与 Server 同机时可得。
    """
    global _usage_cache

    now = time.monotonic()
    if use_cache and _usage_cache and now - _usage_cache[0] < USAGE_CACHE_TTL_SECONDS:
        return _usage_cache[1], _usage_cache[2]

    async with _usage_lock:
        # 等锁期间可能已有采集完成，重新判定以免重复扇出。
        now = time.monotonic()
        if use_cache and _usage_cache and now - _usage_cache[0] < USAGE_CACHE_TTL_SECONDS:
            return _usage_cache[1], _usage_cache[2]

        from core.alive import Alive
        from core.constants import Info
        from .contracts import ProcessAPI
        from .peer import PeerSelector

        usages = []
        for label, pid in ((DAEMON_LABEL, Info.daemon_pid), (HUB_LABEL, Info.hub_pid)):
            external = collect_external_usage(pid)
            if external and (usage := build_usage(label, external)):
                usages.append(usage)

        failures: list[ProcessUnavailable] = []
        try:
            report = await ProcessAPI.resource_usage.with_timeout(USAGE_GATHER_TIMEOUT_SECONDS).gather(
                PeerSelector.all()
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # 扇出整体失败时仍交付非 Peer 进程数据，并以一行说明 Peer 数据整体缺失。
            Logger.exception("Failed to gather per-process resource usage.")
            failures = [ProcessUnavailable(PEERS_LABEL, type(exc).__name__)]
        else:
            peer_usages, failures = summarize_process_usage(report.results, report.errors, dict(Alive.values))
            usages.extend(peer_usages)

        _usage_cache = (time.monotonic(), usages, failures)
        return usages, failures
