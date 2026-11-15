# 开发工作流与代码风格

## 目录

- [依赖管理](#依赖管理)
- [Ruff](#ruff)
- [Pre-commit](#pre-commit)
- [测试前置](#测试前置)
- [分支与提交](#分支与提交)
- [中文排版](#中文排版)
- [只描述当前状态](#只描述当前状态)
- [导入与注释](#导入与注释)

## 依赖管理

使用 uv 管理依赖：

```bash
uv sync
uv add <包名>
uv lock
```

新增依赖后，将其移动到 `pyproject.toml` 对应注释分组并按字母序排列。不要手写 `requirements.txt`；pre-commit 会从锁文件导出。

## Ruff

- 行宽：120。
- 引号：双引号。
- 忽略规则：E402、F405、F403、E741、E721。

```bash
uv run ruff format .
uv run ruff check .
```

## Pre-commit

```bash
pre-commit install
```

`.pre-commit-config.yaml` 会运行：

1. `uv-export`，生成无 hash 的 `requirements.txt`。
2. `ruff-check --fix`。
3. `ruff-format`。

## 测试前置

项目使用自研测试框架（`tester.py`），日常单测使用 `tests/run_one.py`，自动化运行需设置 `CI=1`；完整用法见 `testing.md`。

Windows 下运行包含中文输出的 Python 命令时，在进程启动前设置 `PYTHONIOENCODING=UTF-8`。

## 分支与提交

- 所有改动留在未提交的工作区，仅在用户明确授权时执行 `git commit`、`git add`、`git push`、`git reset`、`git checkout -- <file>` 等改动暂存区、历史或工作区的操作；单次授权仅对当次请求有效。
- 新功能或一般改动：`dev/` 前缀。
- Bug 修复：`fix/` 前缀。
- 分支名使用英文。
- Commit message 使用英文或简体中文，推荐 Conventional Commits。
- PR 需通过 CI，并至少获得一名开发者 LGTM。

## 中文排版

遵循 `CONTRIBUTING.md` 与中文文案排版指北：

- 中英文之间加空格，但链接前后不额外加空格。
- 使用全角中文标点；简体中文使用弯引号“”。
- 专有名词保持正确大小写，如 GitHub、Minecraft、JavaScript。
- 称呼用户使用“你”，不用“您”。
- 机器人自称使用“机器人”；第三人称使用“它”，避免第一人称描述。

这些规则适用于 `zh_cn.json` 中所有面向用户的文案。

## 只描述当前状态

文档、注释和配置说明只描述当前状态與设计取舍，不写“原本是 X，现在改为 Y”等历史对比；变更历史由 git 承载。

例外：代码中为迁移历史数据而保留的兼容逻辑（如旧配置表名、数据库版本升级路径、退役客户端的数据迁移）需保留并注明适用范围；API 弃用标注同样保留。

## 导入与注释

按标准库、第三方库、项目内部模块分组导入。遇到核心循环依赖时使用 `core.exports`。

只在逻辑涉及反直觉的边界情况、hack、复杂算法或特定业务规则时写注释，解释“为什么”而非实现细节。非公开 API 的模块、类、函数不加 docstring。单条注释一般不超过三行，使用正式书面语。

文档面向技术用户与维护者，覆盖功能概述、基本使用步骤和接口实现。配置项注释只描述用途，不描述技术细节。
