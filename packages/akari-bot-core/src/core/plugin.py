"""插件注册表：统一发现平台适配器与模块包。

插件包通过 ``importlib.metadata`` 的 entry point 注册（``akari.bots`` / ``akari.modules``）；
未安装时回退为扫描 ``bots`` / ``modules`` 命名空间包，便于开发期直接运行。
"""

from __future__ import annotations

import importlib.util
import pkgutil
from dataclasses import dataclass
from importlib.metadata import entry_points
from pathlib import Path
from typing import Literal

BOTS_ENTRY_POINT_GROUP = "akari.bots"
MODULES_ENTRY_POINT_GROUP = "akari.modules"

PluginKind = Literal["bot", "module"]


@dataclass(frozen=True)
class PluginPackage:
    kind: PluginKind
    name: str
    package: str
    path: Path

    @property
    def locales_path(self) -> Path:
        return self.path / "locales"

    def subpath(self, *parts: str) -> Path:
        return self.path.joinpath(*parts)


def _package_path(package: str) -> Path | None:
    """取包的源码目录，不执行包本身。"""
    try:
        spec = importlib.util.find_spec(package)
    except (ImportError, ValueError):
        return None
    if spec is None or not spec.submodule_search_locations:
        return None
    return Path(next(iter(spec.submodule_search_locations)))


def _entry_point_packages(group: str, kind: PluginKind) -> list[PluginPackage]:
    packages = []
    for entry_point in sorted(entry_points(group=group), key=lambda item: item.name):
        package = entry_point.value.partition(":")[0].strip()
        path = _package_path(package)
        if path is None:
            continue
        packages.append(PluginPackage(kind, entry_point.name, package, path))
    return packages


def _scanned_packages(namespace: str, kind: PluginKind) -> list[PluginPackage]:
    try:
        spec = importlib.util.find_spec(namespace)
    except (ImportError, ValueError):
        return []
    if spec is None or not spec.submodule_search_locations:
        return []
    packages = []
    for info in sorted(pkgutil.iter_modules(list(spec.submodule_search_locations)), key=lambda item: item.name):
        if not info.ispkg or info.name.startswith(("_", ".")):
            continue
        packages.append(
            PluginPackage(kind, info.name, f"{namespace}.{info.name}", Path(info.module_finder.path) / info.name)
        )
    return packages


def _collect(kind: PluginKind, group: str, namespace: str) -> list[PluginPackage]:
    packages: dict[str, PluginPackage] = {}
    for package in (*_entry_point_packages(group, kind), *_scanned_packages(namespace, kind)):
        packages.setdefault(package.package, package)
    return sorted(packages.values(), key=lambda item: item.name)


def iter_bot_packages() -> list[PluginPackage]:
    """列出全部平台适配器。"""
    return _collect("bot", BOTS_ENTRY_POINT_GROUP, "bots")


def iter_module_packages() -> list[PluginPackage]:
    """列出全部命令模块。"""
    return _collect("module", MODULES_ENTRY_POINT_GROUP, "modules")


def get_module_package(name: str) -> PluginPackage | None:
    return next((package for package in iter_module_packages() if package.name == name), None)


def iter_source_files() -> list[tuple[str, Path]]:
    """列出 core 与全部插件的源码文件，元素为 (逻辑路径, 绝对路径)。"""
    entries = [("core", Path(__file__).resolve().parent)]
    entries += [
        (package.package.replace(".", "/"), package.path) for package in (*iter_bot_packages(), *iter_module_packages())
    ]
    files = []
    for prefix, root in entries:
        for path in sorted(root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            files.append((f"{prefix}/{path.relative_to(root).as_posix()}", path))
    return files
