---
name: akaribot-dev
description: AkariBot 项目开发指南。涵盖核心框架、消息与会话系统、命令模块、平台适配器、配置、数据库、队列、i18n、测试与代码规范；按任务领域读取对应 reference。
---

# AkariBot 开发指南

按任务领域读取对应的一级参考文件；跨领域任务组合读取相关文件。

## 核心约定

- 面向用户的固定文案使用 `I18NContext`，只在对应的 `locales/zh_cn.json` 新增或修改节点，参数占位符使用 `${name}`。其他语言文件由 Weblate 自动同步，`assets/config_store/<语言>/` 由配置生成脚本派生，均不手动修改。
- 新增配置字段时，在所属组件的 `zh_cn.json` 添加 `config.comments.<表名>.<字段名>`；未指定 `table_name` 时表名为 `config`。
- 会话归属的模块数据使用 `union_id` 主键并声明 `union_scope`。
- 平台能力使用 `Features(...)` 实例声明并赋给 `ContextManager.features`。
- `SessionInfo` 会跨进程传输，字段需可序列化；模块代码运行在 server 进程，平台 SDK 操作通过 JobQueue / `ContextManager` 在 bot 进程执行。
- 遇到循环导入时使用 `core.exports` 导出机制。
- 单元测试用 pytest 运行（`uv run pytest tests/unit`），集成测试由 `tester.py` 运行（自动化 `CI=1`）；全量测试交由 CI 执行。
- 文档、注释和配置说明只描述当前状态，不写历史对比；为数据迁移保留的兼容逻辑与 API 弃用标注除外。
- 只在涉及边界情况、复杂算法或特定业务规则时写注释，解释“为什么”，单条一般不超过三行，使用正式书面语；非公开 API 不加 docstring。
- 修改留在工作区，仅在用户明确授权时执行 `git commit` 等版本控制写操作。新功能分支用 `dev/`，修复分支用 `fix/`，英文命名。

## 按领域读取

| 任务 | 参考文件 | 典型内容 |
| --- | --- | --- |
| 理解整体架构、启动、进程、消息流或目录 | [architecture.md](references/architecture.md) | 多进程、JobQueue、启动与重启、收发消息全链路、目录结构 |
| 修改消息、会话、Bot 或 parser | [messaging-and-parser.md](references/messaging-and-parser.md) | Bot、消息元素、SessionInfo、MessageSession、ContextManager、parser、等待与控制流 |
| 修改 loader、component、配置、数据库或队列 | [infrastructure.md](references/infrastructure.md) | 模块加载、注册、配置模板、union 数据、双连接、JobQueue、exports、热重载 |
| 新建或修改命令模块 | [module-development.md](references/module-development.md) | module/command/regex、权限、配置、数据库、i18n、定时任务、hook、交互等待 |
| 新建或修改平台适配器 | [platform-adapters.md](references/platform-adapters.md) | info、Features、bot 入口、ContextManager、私信和平台能力 |
| 编写、运行或诊断测试 | [testing.md](references/testing.md) | pytest 单测、`@func_case` / `@case` 集成测试、Expectation、mock parser、fixture、运行命令 |
| 依赖、格式化、分支或文字排版 | [workflow-and-style.md](references/workflow-and-style.md) | Ruff、pre-commit、依赖、分支、中文排版、导入和注释约定 |

## 组合读取建议

- 修改普通命令：`module-development.md` + `messaging-and-parser.md`（含测试时加 `testing.md`）。
- 修改模块配置或数据库：`module-development.md` + `infrastructure.md`。
- 修改消息元素、会话能力或 parser：`messaging-and-parser.md`（影响命令或测试时加 `module-development.md`、`testing.md`）。
- 修改平台发送、消息渲染或私信：`platform-adapters.md` + `architecture.md` + `messaging-and-parser.md`。
- 修改启动、队列或跨进程行为：`architecture.md` + `infrastructure.md`。

## 高频命令

```bash
uv sync
uv run ruff format .
uv run ruff check .

uv run pytest tests/unit
CI=1 AKARI_TEST_FILTER=<集成文件名子串> uv run python tester.py
CI=1 PYTHONIOENCODING=UTF-8 uv run --no-sync python tests/run_one.py <集成测试文件> [入口函数]
COVERAGE=1 CI=1 uv run python tester.py
```

## 注意事项

- parser 位于 `core/builtins/parser/`，模块加载器位于 `core/loader.py`，测试框架位于 `core/tester/`。
- 测试环境的 mock parser 默认跳过模块启用检查与平台过滤，并将发送者设为 superuser。
- Windows 下运行含中文输出的命令时显式设置 `PYTHONIOENCODING=UTF-8`。
- `.bot.lock` 用于单实例互斥；`pre_init()` 每次启动会清空 `cache/` 目录。
- 修改 reference 后可运行 `uv run python .agents/skills/akaribot-dev/scripts/validate_references.py` 校验文档结构与链接。
