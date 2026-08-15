"""根据 Git 变更范围生成子进程重启计划。"""

import importlib
from dataclasses import dataclass
from enum import Enum


RESTART_ALL_EXIT_CODE = 233
RESTART_PROCESS_EXIT_CODE = 234


class RestartScope(Enum):
    """自动重启能够覆盖的进程范围。"""

    ALL = "all"
    SERVER = "server"
    BOTS = "bots"
    MANUAL = "manual"


@dataclass(frozen=True)
class RestartPlan:
    """一次重启应覆盖的进程。"""

    scope: RestartScope
    bots: tuple[str, ...] = ()


def normalize_git_path(path: str) -> str:
    """把 Git 路径统一为仓库内的 POSIX 相对路径。"""
    normalized = path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.strip("/")


def parse_git_diff_paths(output: str) -> tuple[str, ...]:
    """解析 ``git diff --name-only -z`` 的输出。"""
    return tuple(normalize_git_path(path) for path in output.split("\0") if path)


def _requires_pre_init(path: str) -> bool:
    parts = path.split("/")
    if len(parts) < 3 or parts[0] not in {"bots", "modules"}:
        return False
    if parts[-1] == "config.py":
        return True
    # 客户端名称是 server 与现有 bot 进程之间的队列路由键，运行中不能只改一侧。
    if parts[0] == "bots" and parts[-1] == "info.py":
        return True
    # 平台语言快照也会被 server 使用，仅重启平台进程不足以加载完整变更。
    return parts[0] == "bots" and "locales" in parts[2:]


def classify_restart_paths(changed_paths: tuple[str, ...] | list[str], available_bots: set[str]) -> RestartPlan:
    """按 pull 前后发生变化的路径选择最小安全重启范围。

    无法明确归类的根目录文件、混合目录变更和未知平台均回退到全量重启。
    """
    paths = tuple(normalize_git_path(path) for path in changed_paths if path)
    if not paths:
        return RestartPlan(RestartScope.ALL)
    if "bot.py" in paths:
        return RestartPlan(RestartScope.MANUAL)
    if any(_requires_pre_init(path) for path in paths):
        return RestartPlan(RestartScope.ALL)
    if all(path.startswith("modules/") for path in paths):
        return RestartPlan(RestartScope.SERVER)
    if all(path.startswith("bots/") for path in paths):
        bots = set()
        for path in paths:
            parts = path.split("/")
            if len(parts) < 3 or parts[1] not in available_bots:
                return RestartPlan(RestartScope.ALL)
            bots.add(parts[1])
        return RestartPlan(RestartScope.BOTS, tuple(sorted(bots)))
    return RestartPlan(RestartScope.ALL)


def get_bot_client_name(bot_name: str) -> str | None:
    """把 ``bots/<目录>`` 映射为队列使用的客户端名称。"""
    try:
        client_name = importlib.import_module(f"bots.{bot_name}.info").client_name
    except Exception:
        return None
    return client_name if isinstance(client_name, str) and client_name else None
