"""依赖分层检查：静态扫描 core / bots / modules 的导入方向。

分层从框架到插件依次为 ``core`` < ``modules/core`` < ``bots/*``、``modules/*``。
框架不得反向依赖插件，插件只能使用框架公开 API。
``tools/layers_baseline.json`` 记录尚未清理的越界，只允许缩减。
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parent.parent
BASELINE_FILE = ROOT / "tools" / "layers_baseline.json"
PACKAGES_DIR = ROOT / "packages"

# 平台 SDK 只允许出现在 bots/ 下，模块跨层依赖 SDK 会让依赖声明无法按成员拆分。
PLATFORM_SDK = frozenset({"aiocqhttp", "aiogram", "botpy", "discord", "khl", "launart", "milky", "nio", "satori"})

CORE_PUBLIC_FOR_BOTS = (
    "core.builtins.bot",
    "core.builtins.config",
    "core.builtins.message",
    "core.builtins.session",
    "core.builtins.temp",
    "core.builtins.utils",
    "core.client",
    "core.config",
    "core.constants",
    "core.database",
    "core.i18n",
    "core.logger",
    "core.plugin",
    "core.queue.contracts",
    "core.smtp",
    "core.utils",
)

# 普通模块可用的框架 API。改动这里等于改动对外契约，需同步模块开发文档。
CORE_PUBLIC_FOR_PLUGINS = (
    "core.builtins.bot",
    "core.builtins.config",
    "core.builtins.filter",
    "core.builtins.message",
    "core.builtins.parser.args",
    "core.builtins.session",
    "core.builtins.utils",
    "core.component",
    "core.config",
    "core.constants",
    "core.database.base",
    "core.database.models",
    "core.i18n",
    "core.logger",
    "core.plugin",
    "core.queue.contracts",
    "core.queue.errors",
    "core.scheduler",
    "core.types",
    "core.utils",
)

# modules/core 承担 parser 策略与框架管理命令，额外放行引擎内部接口。
CORE_PUBLIC_FOR_BUILTIN_PLUGINS = CORE_PUBLIC_FOR_PLUGINS + (
    "core.alive",
    "core.builtins.converter",
    "core.builtins.parser",
    "core.database",
    "core.exports",
    "core.loader",
    "core.module_runtime",
    "core.queue.diagnostics",
    "core.queue.server",
    "core.server.terminate",
    "core.smtp",
)


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    rule: str
    target: str
    message: str
    severity: str = "error"


def area_of(rel_path: Path) -> str:
    parts = rel_path.parts
    if parts[0] in ("bots", "modules") and len(parts) > 1:
        return f"{parts[0]}/{parts[1]}"
    return parts[0]


def module_area(module_name: str) -> str:
    parts = module_name.split(".")
    if parts[0] in ("bots", "modules") and len(parts) > 1:
        return f"{parts[0]}/{parts[1]}"
    return parts[0]


def iter_imports(path: Path) -> Iterator[tuple[int, str]]:
    """产出 (行号, 绝对模块名)，跳过相对导入。"""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                yield node.lineno, node.module
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if name not in ("import_module", "__import__") or not node.args:
                continue
            arg = node.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                yield node.lineno, arg.value


def matches(module_name: str, prefixes: tuple[str, ...]) -> bool:
    return any(module_name == prefix or module_name.startswith(f"{prefix}.") for prefix in prefixes)


def check_file(rel_path: Path, abs_path: Path) -> Iterator[Violation]:
    area = area_of(rel_path)
    rel = rel_path.as_posix()
    for line, target in iter_imports(abs_path):
        top = target.split(".")[0]
        if top in PLATFORM_SDK:
            if area.startswith("modules/"):
                yield Violation(rel, line, "R8", target, "模块不得依赖平台 SDK")
            continue
        if top not in ("core", "bots", "modules"):
            continue
        target_area = module_area(target)
        if target_area == area:
            continue

        if area == "core":
            yield Violation(rel, line, "R1", target, f"框架 core 不得依赖插件 {target_area}")
        elif area.startswith("bots/"):
            if target.split(".")[0] == "modules":
                yield Violation(rel, line, "R3", target, "平台适配器不得依赖模块")
            elif target.split(".")[0] == "bots":
                yield Violation(rel, line, "R7", target, "平台适配器之间不得互相依赖")
            elif not matches(target, CORE_PUBLIC_FOR_BOTS):
                yield Violation(rel, line, "R5", target, "平台适配器使用了框架内部接口")
        else:
            if target.split(".")[0] == "bots":
                yield Violation(rel, line, "R2", target, "模块不得依赖平台适配器")
            elif target.split(".")[0] == "modules":
                yield Violation(
                    rel,
                    line,
                    "R6",
                    target,
                    f"模块之间不得互相依赖（{target_area}）",
                    severity="warning",
                )
            elif target.split(".")[0] in PLATFORM_SDK:
                yield Violation(rel, line, "R8", target, "模块不得依赖平台 SDK")
            else:
                allowed = CORE_PUBLIC_FOR_BUILTIN_PLUGINS if area == "modules/core" else CORE_PUBLIC_FOR_PLUGINS
                if not matches(target, allowed):
                    yield Violation(rel, line, "R4", target, "模块使用了框架内部接口")


def iter_sources() -> Iterator[tuple[Path, Path]]:
    """产出 (源码根目录, 文件路径)，逻辑路径相对源码根目录。"""
    for member in sorted(PACKAGES_DIR.iterdir()):
        src = member / "src"
        if not src.is_dir():
            continue
        for path in sorted(src.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            yield src, path


def collect() -> list[Violation]:
    violations = []
    for src, path in iter_sources():
        violations.extend(check_file(path.relative_to(src), path))
    return violations


def load_baseline() -> dict[str, list[str]]:
    if not BASELINE_FILE.exists():
        return {}
    return json.loads(BASELINE_FILE.read_text(encoding="utf-8"))


def save_baseline(baseline: dict[str, list[str]]) -> None:
    text = json.dumps(dict(sorted(baseline.items())), indent=2, ensure_ascii=False)
    BASELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_FILE.write_text(f"{text}\n", encoding="utf-8", newline="\n")


def partition(
    violations: list[Violation], baseline: dict[str, list[str]]
) -> tuple[list[Violation], list[Violation], list[str]]:
    """按基线拆分出新增违规、已登记违规与失效的基线条目。"""
    fresh, baselined, used = [], [], set()
    for violation in violations:
        prefixes = baseline.get(violation.path, [])
        hit = next((prefix for prefix in prefixes if matches(violation.target, (prefix,))), None)
        if hit is None:
            fresh.append(violation)
            continue
        baselined.append(violation)
        used.add((violation.path, hit))
    stale = [
        f"{path}: {prefix}" for path, prefixes in baseline.items() for prefix in prefixes if (path, prefix) not in used
    ]
    return fresh, baselined, stale


def rebuild_baseline(violations: list[Violation]) -> dict[str, list[str]]:
    baseline: dict[str, list[str]] = {}
    for violation in violations:
        prefixes = baseline.setdefault(violation.path, [])
        if violation.target not in prefixes:
            prefixes.append(violation.target)
    for prefixes in baseline.values():
        prefixes.sort()
    return baseline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="检查 core / bots / modules 的依赖方向")
    parser.add_argument("--update-baseline", action="store_true", help="用当前违规重写基线文件")
    parser.add_argument("--strict", action="store_true", help="把警告也视为失败")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    args = parser.parse_args(argv)

    violations = collect()
    if args.update_baseline:
        save_baseline(rebuild_baseline(violations))
        print(f"基线已更新：{BASELINE_FILE.relative_to(ROOT).as_posix()}（{len(violations)} 条）")
        return 0

    fresh, baselined, stale = partition(violations, load_baseline())
    errors = [violation for violation in fresh if violation.severity == "error"]
    warnings = [violation for violation in fresh if violation.severity != "error"]

    if args.json:
        print(
            json.dumps(
                {
                    "errors": [violation.__dict__ for violation in errors],
                    "warnings": [violation.__dict__ for violation in warnings],
                    "baselined": [violation.__dict__ for violation in baselined],
                    "stale": stale,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        for violation in errors:
            print(f"{violation.path}:{violation.line}: [{violation.rule}] {violation.message}: {violation.target}")
        for violation in warnings:
            print(f"{violation.path}:{violation.line}: [{violation.rule}] 警告 {violation.message}: {violation.target}")
        for entry in stale:
            print(f"基线条目未命中，请运行 --update-baseline 清理：{entry}")
        print(
            f"\n新增违规 {len(errors)} 条，警告 {len(warnings)} 条，"
            f"基线内 {len(baselined)} 条，未命中基线 {len(stale)} 条。"
        )

    if errors or (args.strict and warnings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
