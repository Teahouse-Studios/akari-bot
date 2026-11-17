"""依赖声明一致性检查：校验 packages/ 成员清单、entry point 与根项目聚合。

规则：

1. 成员目录名与 ``project.name`` 一致，且每个成员都以 ``akari-bot-core`` 作为依赖。
2. 每个平台适配器与模块都有对应的根项目 extra，extra 只引用该成员。
3. 插件成员声明了 entry point 与 ``uv_build`` 的模块路径，导入名与目录名一致。
4. 根项目的依赖只能是工作区成员；第三方依赖只能出现在成员的清单里。
5. 同一依赖在多处声明时版本约束必须一致。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGES_DIR = ROOT / "packages"

CORE_MEMBER = "akari-bot-core"
ADAPTER_MEMBER_PREFIX = "akari-bot-adapter-"
ADAPTER_EXTRA_PREFIX = "bots-"
ADAPTER_ENTRY_POINT_GROUP = "akari.bots"
ADAPTER_IMPORT_PREFIX = "bots"
MODULE_MEMBER_PREFIX = "akari-bot-module-"
MODULE_EXTRA_PREFIX = "modules-"
MODULE_ENTRY_POINT_GROUP = "akari.modules"
MODULE_IMPORT_PREFIX = "modules"

# 只属于开发流程、不归属任何成员的依赖。
ROOT_ONLY = {"coverage", "pre-commit", "pytest", "ruff"}

REQUIREMENT_PATTERN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)")


def normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def split_requirement(text: str) -> tuple[str, str]:
    """拆出 (规范化名称, 规范化版本约束)，忽略 extras 与环境标记。"""
    body = text.split(";", 1)[0].strip()
    match = REQUIREMENT_PATTERN.match(body)
    if not match:
        raise ValueError(f"无法解析依赖声明：{text}")
    rest = body[match.end() :]
    rest = re.sub(r"^\[[^\]]*\]", "", rest)
    return normalize(match.group(1)), re.sub(r"\s+", "", rest)


def load_pyproject(path: Path) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def collect_members() -> dict[str, dict]:
    members = {}
    for path in sorted(PACKAGES_DIR.glob("*/pyproject.toml")):
        data = load_pyproject(path)
        project = data.get("project", {})
        name = project.get("name")
        if not name:
            raise SystemExit(f"{path.relative_to(ROOT).as_posix()}: 缺少 project.name")
        if name in members:
            raise SystemExit(f"成员名称重复：{name}")
        build_backend = data.get("tool", {}).get("uv", {}).get("build-backend", {})
        members[name] = {
            "path": path.relative_to(ROOT).as_posix(),
            "directory": path.parent.name,
            "version": project.get("version", ""),
            "dependencies": project.get("dependencies", []),
            "entry_points": project.get("entry-points", {}),
            "build": build_backend,
        }
    return members


def plugin_expectations(member: str) -> dict | None:
    """给出适配器／模块成员的 extra、entry point 与导入名预期。"""
    if member.startswith(ADAPTER_MEMBER_PREFIX):
        name = member[len(ADAPTER_MEMBER_PREFIX) :]
        return {
            "extra": f"{ADAPTER_EXTRA_PREFIX}{name}",
            "entry_point_group": ADAPTER_ENTRY_POINT_GROUP,
            "import_name": f"{ADAPTER_IMPORT_PREFIX}.{name}",
        }
    if member.startswith(MODULE_MEMBER_PREFIX):
        name = member[len(MODULE_MEMBER_PREFIX) :]
        return {
            "extra": f"{MODULE_EXTRA_PREFIX}{name}",
            "entry_point_group": MODULE_ENTRY_POINT_GROUP,
            "import_name": f"{MODULE_IMPORT_PREFIX}.{name}",
        }
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="检查 packages 成员清单、entry point 与根项目聚合")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    args = parser.parse_args(argv)

    root_project = load_pyproject(ROOT / "pyproject.toml")
    root_version = root_project["project"]["version"]
    root_dependencies = root_project["project"].get("dependencies", [])
    extras = root_project["project"].get("optional-dependencies", {})
    dev = root_project.get("dependency-groups", {}).get("dev", [])
    members = collect_members()

    errors: list[str] = []
    warnings: list[str] = []

    root_dep_names = [split_requirement(dep)[0] for dep in root_dependencies]
    if root_dep_names != [normalize(CORE_MEMBER)]:
        errors.append(f"根项目 dependencies 应只包含 {CORE_MEMBER}，实际为 {root_dependencies}")

    for name, member in members.items():
        if member["directory"] != name:
            errors.append(f"成员目录 {member['directory']} 与 project.name {name} 不一致")
        if member["version"] != root_version:
            warnings.append(f"成员 {name} 的版本 {member['version']} 与根项目 {root_version} 不一致")
        if name == CORE_MEMBER:
            continue

        declared = {split_requirement(dep)[0] for dep in member["dependencies"]}
        if normalize(CORE_MEMBER) not in declared:
            errors.append(f"成员 {name} 未声明依赖 {CORE_MEMBER}")

        expectation = plugin_expectations(name)
        if expectation is None:
            errors.append(f"成员 {name} 既不是平台适配器也不是模块")
            continue
        extra_values = extras.get(expectation["extra"], [])
        if [normalize(value) for value in extra_values] != [normalize(name)]:
            errors.append(f"extra {expectation['extra']} 应只引用 {name}，实际为 {extra_values}")
        entry_points = member["entry_points"].get(expectation["entry_point_group"], {})
        if list(entry_points.values()) != [expectation["import_name"]]:
            errors.append(
                f"成员 {name} 应在 {expectation['entry_point_group']} 注册 {expectation['import_name']}，"
                f"实际为 {entry_points}"
            )
        if member["build"].get("module-name") != expectation["import_name"]:
            errors.append(f"成员 {name} 的 module-name 应为 {expectation['import_name']}")
        if member["build"].get("namespace") is not True:
            errors.append(f"成员 {name} 需要开启命名空间包构建（namespace = true）")

    for extra, values in extras.items():
        matched = [member for member in members if (plugin_expectations(member) or {}).get("extra") == extra]
        if not matched:
            errors.append(f"extra {extra} 没有对应的成员")
            continue
        if [normalize(value) for value in values] != [normalize(matched[0])]:
            errors.append(f"extra {extra} 的取值应只包含 {matched[0]}")

    declared: dict[str, list[tuple[str, str]]] = {}
    for name, member in members.items():
        for requirement in member["dependencies"]:
            dep, spec = split_requirement(requirement)
            declared.setdefault(dep, []).append((name, spec))
    for dep, entries in declared.items():
        specs = {spec for _, spec in entries}
        if len(specs) > 1:
            detail = "; ".join(f"{name}: {spec or '无约束'}" for name, spec in entries)
            errors.append(f"依赖 {dep} 的版本约束不一致 -> {detail}")

    root_only = {normalize(value) for value in ROOT_ONLY}
    for requirement in dev:
        dep, _ = split_requirement(requirement)
        if dep not in root_only:
            warnings.append(f"开发依赖 {dep} 未登记在 ROOT_ONLY 中")

    if args.json:
        print(json.dumps({"errors": errors, "warnings": warnings}, indent=2, ensure_ascii=False))
    else:
        for message in errors:
            print(f"错误：{message}")
        for message in warnings:
            print(f"警告：{message}")
        print(f"\n成员 {len(members)} 个，错误 {len(errors)} 条，警告 {len(warnings)} 条。")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
